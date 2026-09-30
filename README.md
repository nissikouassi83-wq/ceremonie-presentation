# Enquête de satisfaction — Cérémonie IM2S (Catalogue 2027)

- Questionnaire : `/` (5 étapes, 16 questions)
- Tableau de bord : `/admin/reponses?cle=VOTRE_CLE`
- Export CSV : `/admin/export.csv?cle=VOTRE_CLE`

## Déploiement sur Vercel
Le point d’entrée serverless est `api/index.py` et `vercel.json` redirige les requêtes vers Flask.

1. Installer la CLI Vercel et se connecter avec `vercel login`.
2. Depuis ce dossier, lancer `vercel` pour créer le projet et effectuer un déploiement de prévisualisation.
3. Dans les paramètres du projet Vercel, définir `SECRET_KEY` et `ADMIN_KEY` avec des valeurs privées et solides.
4. Lancer `vercel --prod` pour publier en production.

**Important :** Vercel ne conserve pas de façon fiable les fichiers écrits localement par une fonction serverless. Les réponses actuelles sont enregistrées dans `data/reponses.csv`; configurez un stockage persistant (par exemple Supabase) avant d’utiliser ce déploiement pour une collecte réelle. Sans cela, des réponses peuvent être perdues ou être différentes selon l’instance utilisée.

## Déploiement sur Render
1. Mettre le contenu du dossier dans un dépôt GitHub.
2. Render → New → Web Service → choisir le dépôt (render.yaml est détecté).
3. Dans Environment, définir `ADMIN_KEY` (clé solide, non devinable). `SECRET_KEY` est généré automatiquement.

## Attention : stockage
Les réponses sont écrites dans `data/reponses.csv`. Sur le plan gratuit de Render, le disque est
éphémère : le fichier peut être effacé à chaque redéploiement ou redémarrage.
Exportez le CSV régulièrement, ou passez à une base externe (Supabase, Neon).
