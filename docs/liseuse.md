# Lire Signal Matin sur une liseuse

Signal Matin peut produire une édition numérique conçue pour les écrans e-ink.
Cela évite l'impression tout en conservant une lecture calme, hors des réseaux
sociaux et des notifications du téléphone.

## Quel format choisir ?

### EPUB — recommandé

L'EPUB est reformatable : la liseuse adapte les lignes à son écran et permet de
changer la police, la taille du texte, les marges et l'interligne. Le sommaire
donne un accès direct à la une, la journée, l'actualité, la tech, la veille et
les jeux.

```powershell
signal-matin ereader --demo
```

Le fichier est créé dans :

```text
output/ereader/AAAA-MM-JJ-signal-matin.epub
```

### PDF e-ink — mise en page stable

Le PDF e-ink utilise un ratio 3:4, une seule colonne, une police plus grande et
un contraste élevé. Il est utile lorsqu'une liseuse gère mal l'EPUB ou lorsqu'on
souhaite conserver exactement la même composition.

```powershell
signal-matin ereader --demo --format pdf
```

Trois tailles sont disponibles :

```powershell
signal-matin ereader --demo --format pdf --screen small
signal-matin ereader --demo --format pdf --screen medium
signal-matin ereader --demo --format pdf --screen large
```

Le profil `medium` est le choix générique. L'EPUB n'a pas besoin de profil : il
s'adapte directement à la liseuse.

Pour comparer les deux sorties :

```powershell
signal-matin ereader --demo --format both
```

## Transférer le journal

La méthode exacte dépend du modèle de liseuse :

1. générer d'abord l'EPUB et le PDF e-ink ;
2. connecter la liseuse en USB ou utiliser son service d'envoi de documents ;
3. placer le fichier dans le dossier de livres ou de documents indiqué par le
   fabricant ;
4. éjecter proprement l'appareil ;
5. vérifier le sommaire, la taille des caractères et les changements de page.

Ne pas automatiser la copie vers un appareil avant d'avoir validé manuellement
le bon dossier et le bon format sur ce modèle précis.

## Utiliser ses vraies données

Retire `--demo` lorsque `config.yaml` est prêt :

```powershell
signal-matin ereader --live --format epub
```

Les règles de confidentialité restent identiques : l'édition générée est un
fichier personnel et ne doit pas être ajoutée au dépôt Git.
