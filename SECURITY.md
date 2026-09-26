# Sécurité et confidentialité

N'ouvre pas d'issue publique contenant une clé, un token OAuth, une URL de
calendrier privée, un nom d'imprimante ou un PDF personnel.

Si un secret a été commité, révoque-le immédiatement puis nettoie l'historique.
La suppression du fichier dans un commit ultérieur ne suffit pas.

Les sorties, `.env`, `config.yaml`, fichiers OAuth et calendriers ICS sont
ignorés par défaut. Vérifie toujours `git status` avant un push.

Pour signaler une vulnérabilité sans publier de détails exploitables, utilise la
fonction de signalement privé de sécurité du dépôt GitHub.
