import csv
import io
import os
import threading
from datetime import datetime

from flask import (Flask, Response, abort, redirect, render_template, request,
                   session, url_for)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "changez-moi-en-production")
ADMIN_KEY = os.environ.get("ADMIN_KEY", "ceremonie2026")
DATA_DIR = os.environ.get("DATA_DIR", os.path.join(os.path.dirname(__file__), "data"))
CSV_PATH = os.path.join(DATA_DIR, "reponses.csv")
LOCK = threading.Lock()

SAT4 = ["Très satisfait(e)", "Satisfait(e)", "Insatisfait(e)", "Très insatisfait(e)"]
AGREE4 = ["Tout à fait d’accord", "Plutôt d’accord", "Plutôt pas d’accord", "Pas du tout d’accord"]
SCORE = dict(zip(SAT4, [4, 3, 2, 1]))
SCORE.update(dict(zip(AGREE4, [4, 3, 2, 1])))
CSAT5 = ["Très satisfait(e)", "Satisfait(e)", "Neutre", "Insatisfait(e)", "Très insatisfait(e)"]

Q_ROLE = ["Entreprise cliente du Centre de Perfectionnement", "Entreprise prospect",
          "Responsable RH / formation", "Partenaire institutionnel", "Représentant du FDFP",
          "Organisation professionnelle", "Collaborateur CNPS / IM2S", "Autre"]
Q_FONCTION = ["Dirigeant(e) / chef d’entreprise", "DRH / Responsable formation",
              "Responsable développement des compétences", "Autre"]
Q_MODE = ["En présentiel (Auditorium)", "En ligne (streaming)"]
Q_CANAL = ["Invitation de l’IM2S / CNPS", "Relation commerciale / chargé de compte",
           "Réseaux sociaux", "Bouche-à-oreille", "Autre"]
Q_SEXE = ["Masculin", "Féminin"]
Q_PROG = ["Oui, certainement", "Probablement", "Pas encore décidé", "Non"]
Q_FDFP = ["Oui, c’était déjà prévu", "Oui, suite à cette cérémonie", "Pas encore décidé", "Non concerné"]

SEQUENCES = [
    "Accueil et enregistrement des participants", "Mot de bienvenue et allocutions",
    "Présentation du Centre de Perfectionnement", "Présentation du catalogue de formation 2027",
    "Conférence thématique (solutions numériques de la CNPS)",
    "Échanges avec les participants (questions-réponses)",
    "Cérémonie de distinction des entreprises partenaires", "Cocktail / réseautage"]
LOGISTIQUE = [
    "Qualité de l’accueil et de l’enregistrement", "Confort et équipement de la salle (auditorium)",
    "Respect des horaires et du timing", "Qualité du son et des supports visuels",
    "Qualité de la restauration (cocktail)",
    "Qualité de la diffusion en ligne (si participation à distance)"]
AFFIRMATIONS = [
    "Le catalogue 2027 répond aux besoins de formation de mon entreprise",
    "Les nouvelles thématiques proposées sont pertinentes",
    "Le calendrier des séminaires interentreprises 2027 est clair et adapté",
    "La conférence thématique m’a apporté des informations utiles",
    "J’ai une meilleure compréhension de l’échéance FDFP (dépôt des plans de formation avant le 31 octobre 2026)",
    "Les informations reçues faciliteront ma décision de programmer des formations"]


def matrix(qid, labels, options, optional_idx=()):
    return [(f"{qid}_{i + 1}", lab, options, i in optional_idx) for i, lab in enumerate(labels)]


# kind: radio | matrix | nps | text
STEPS = [
    {"title": "Votre profil", "questions": [
        {"id": "q1", "num": "I", "kind": "radio", "label": "Vous participez à cette cérémonie en tant que :", "options": Q_ROLE, "other": True, "required": True},
        {"id": "q2", "num": "II", "kind": "radio", "label": "Quelle est votre fonction principale ?", "options": Q_FONCTION, "other": True, "required": True},
        {"id": "q3", "num": "III", "kind": "radio", "label": "Comment avez-vous participé à la cérémonie ?", "options": Q_MODE, "required": True},
        {"id": "q4", "num": "IV", "kind": "radio", "label": "Comment avez-vous eu connaissance de l’événement ?", "options": Q_CANAL, "other": True, "required": True},
        {"id": "q5", "num": "V", "kind": "radio", "label": "Sexe", "options": Q_SEXE, "required": True},
    ]},
    {"title": "Satisfaction et séquences", "questions": [
        {"id": "q6", "num": "VI", "kind": "radio", "label": "Globalement, quel est votre niveau de satisfaction à l’égard de cette cérémonie ? (CSAT)", "options": CSAT5, "required": True},
        {"id": "q7", "num": "VII", "kind": "matrix", "label": "Comment évaluez-vous chacune des séquences de la cérémonie ?", "hint": "Laissez vide une séquence à laquelle vous n’avez pas assisté.", "rows": matrix("q7", SEQUENCES, SAT4, optional_idx=range(len(SEQUENCES))), "cols": SAT4},
    ]},
    {"title": "Organisation et contenu", "questions": [
        {"id": "q8", "num": "VIII", "kind": "matrix", "label": "Comment évaluez-vous l’organisation et la logistique ?", "hint": "La diffusion en ligne ne concerne que les participants à distance.", "rows": matrix("q8", LOGISTIQUE, SAT4, optional_idx=(5,)), "cols": SAT4},
        {"id": "q9", "num": "IX", "kind": "matrix", "label": "Dans quelle mesure êtes-vous d’accord avec les affirmations suivantes ?", "rows": matrix("q9", AFFIRMATIONS, AGREE4), "cols": AGREE4},
    ]},
    {"title": "Intentions et recommandation", "questions": [
        {"id": "q10", "num": "X", "kind": "radio", "label": "À l’issue de cette cérémonie, comptez-vous programmer des formations avec le Centre de Perfectionnement en 2027 ?", "options": Q_PROG, "required": True},
        {"id": "q11", "num": "XI", "kind": "radio", "label": "Comptez-vous déposer un plan de formation auprès du FDFP au titre de 2027 ?", "options": Q_FDFP, "required": True},
        {"id": "q12", "num": "XII", "kind": "nps", "label": "Quelle est la probabilité que vous recommandiez à un confrère de participer aux événements et aux formations de l’IM2S ? (NPS)", "required": True},
    ]},
    {"title": "Vos commentaires", "questions": [
        {"id": "q13", "num": "XIII", "kind": "text", "label": "Pour quelle raison principale donnez-vous cette note ?"},
        {"id": "q14", "num": "XIV", "kind": "text", "label": "Qu’avez-vous le plus apprécié lors de cette cérémonie ? (points forts)"},
        {"id": "q15", "num": "XV", "kind": "text", "label": "Quels points de friction ou d’amélioration souhaitez-vous signaler en priorité ?"},
        {"id": "q16", "num": "XVI", "kind": "text", "label": "Quelles thématiques de formation souhaiteriez-vous voir programmées en 2027 ?"},
    ]},
]


def all_fields():
    cols = ["date"]
    for step in STEPS:
        for q in step["questions"]:
            if q["kind"] == "matrix":
                cols += [r[0] for r in q["rows"]]
            else:
                cols.append(q["id"])
                if q.get("other"):
                    cols.append(q["id"] + "_autre")
    return cols


FIELDS = all_fields()


def load_rows():
    if not os.path.exists(CSV_PATH):
        return []
    with LOCK, open(CSV_PATH, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def save_row(row):
    os.makedirs(DATA_DIR, exist_ok=True)
    with LOCK:
        new = not os.path.exists(CSV_PATH)
        with open(CSV_PATH, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=FIELDS, extrasaction="ignore")
            if new:
                w.writeheader()
            w.writerow(row)


# ------------------------------------------------------------------ questionnaire
@app.route("/")
def accueil():
    session.clear()
    return render_template("accueil.html", nb_q=16)


@app.route("/etape/<int:n>", methods=["GET", "POST"])
def etape(n):
    if n < 1 or n > len(STEPS):
        abort(404)
    if n > session.get("ok", 0) + 1:
        return redirect(url_for("etape", n=session.get("ok", 0) + 1))
    step = STEPS[n - 1]
    answers = session.get("answers", {})
    errors = set()

    if request.method == "POST":
        f = request.form
        for q in step["questions"]:
            qid = q["id"]
            if q["kind"] == "matrix":
                for key, _, _, optional in q["rows"]:
                    v = f.get(key, "")
                    answers[key] = v
                    if not v and not optional:
                        errors.add(key)
            elif q["kind"] == "text":
                answers[qid] = f.get(qid, "").strip()[:1000]
            else:
                v = f.get(qid, "")
                answers[qid] = v
                if q.get("other"):
                    answers[qid + "_autre"] = f.get(qid + "_autre", "").strip()[:200] if v == "Autre" else ""
                if q["kind"] == "nps" and v and v not in [str(i) for i in range(11)]:
                    v = answers[qid] = ""
                if q["kind"] == "radio" and v and v not in q["options"]:
                    v = answers[qid] = ""
                if q.get("required") and not v:
                    errors.add(qid)
        session["answers"] = answers
        if not errors:
            session["ok"] = max(session.get("ok", 0), n)
            if n == len(STEPS):
                row = dict(answers)
                row["date"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_row(row)
                session.clear()
                return redirect(url_for("merci"))
            return redirect(url_for("etape", n=n + 1))

    return render_template("etape.html", step=step, n=n, total=len(STEPS),
                           a=answers, errors=errors)


@app.route("/merci")
def merci():
    return render_template("merci.html")


# ------------------------------------------------------------------ dashboard
def check_key():
    if request.args.get("cle") != ADMIN_KEY:
        abort(403)


def dist(rows, key, options):
    total = sum(1 for r in rows if r.get(key))
    out = []
    for o in options:
        c = sum(1 for r in rows if r.get(key) == o)
        out.append({"label": o, "n": c, "pct": round(100 * c / total, 1) if total else 0})
    return out


def mean_of(rows, key):
    vals = [SCORE[r[key]] for r in rows if r.get(key) in SCORE]
    return (round(sum(vals) / len(vals), 2), len(vals)) if vals else (None, 0)


def nps_of(rows):
    s = [int(r["q12"]) for r in rows if r.get("q12", "").isdigit()]
    if not s:
        return None
    p = sum(1 for x in s if x >= 9)
    d = sum(1 for x in s if x <= 6)
    return round(100 * (p - d) / len(s))


def csat_of(rows):
    v = [r["q6"] for r in rows if r.get("q6")]
    if not v:
        return None
    return round(100 * sum(1 for x in v if x in CSAT5[:2]) / len(v))


def matrix_stats(rows, q):
    items = []
    for key, label, _, _ in q["rows"]:
        m, n = mean_of(rows, key)
        items.append({"label": label, "mean": m, "n": n,
                      "pct": round(m / 4 * 100) if m else 0,
                      "sat": round(100 * sum(1 for r in rows if SCORE.get(r.get(key), 0) >= 3) / n) if n else None})
    return items


@app.route("/admin/reponses")
def admin():
    check_key()
    rows = load_rows()
    flt = request.args.get("mode", "")
    if flt in Q_MODE:
        rows = [r for r in rows if r.get("q3") == flt]

    qmap = {q["id"]: q for s in STEPS for q in s["questions"]}
    nps_vals = [int(r["q12"]) for r in rows if r.get("q12", "").isdigit()]
    nps_dist = [{"label": str(i), "n": nps_vals.count(i),
                 "pct": round(100 * nps_vals.count(i) / len(nps_vals), 1) if nps_vals else 0} for i in range(11)]
    promo = sum(1 for x in nps_vals if x >= 9)
    passif = sum(1 for x in nps_vals if 7 <= x <= 8)
    detr = sum(1 for x in nps_vals if x <= 6)

    by_sex = []
    for sx in Q_SEXE:
        sub = [r for r in rows if r.get("q5") == sx]
        by_sex.append({"label": sx, "n": len(sub), "csat": csat_of(sub), "nps": nps_of(sub)})

    prog_yes = [r for r in rows if r.get("q10") in Q_PROG[:2]]
    comments = {}
    for k in ("q13", "q14", "q15", "q16"):
        comments[k] = [(r["date"][:10], r[k]) for r in reversed(rows) if r.get(k)][:40]

    return render_template(
        "admin.html", key=ADMIN_KEY, flt=flt, modes=Q_MODE, total=len(rows),
        csat=csat_of(rows), nps=nps_of(rows),
        prog_pct=round(100 * len(prog_yes) / len(rows)) if rows else None,
        fdfp_pct=round(100 * sum(1 for r in rows if r.get("q11") == Q_FDFP[1]) / len(rows)) if rows else None,
        csat_dist=dist(rows, "q6", CSAT5), nps_dist=nps_dist,
        nps_parts={"promo": promo, "passif": passif, "detr": detr},
        roles=dist(rows, "q1", Q_ROLE), modes_d=dist(rows, "q3", Q_MODE),
        canaux=dist(rows, "q4", Q_CANAL), sexes=dist(rows, "q5", Q_SEXE), by_sex=by_sex,
        seq=matrix_stats(rows, qmap["q7"]), logi=matrix_stats(rows, qmap["q8"]),
        aff=matrix_stats(rows, qmap["q9"]),
        prog=dist(rows, "q10", Q_PROG), fdfp=dist(rows, "q11", Q_FDFP),
        comments=comments, titles={k: qmap[k]["label"] for k in comments},
        last=list(reversed(rows))[:15])


@app.route("/admin/export.csv")
def export():
    check_key()
    rows = load_rows()
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FIELDS, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    return Response("\ufeff" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=enquete_ceremonie_2027.csv"})


if __name__ == "__main__":
    app.run(debug=True)
