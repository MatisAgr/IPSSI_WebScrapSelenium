<div align="center">

# Doctolib Scraper

[![wakatime](https://wakatime.com/badge/user/a16f794f-b91d-4818-8dfc-d768ce605ece/project/b93013d7-aceb-45a4-a283-f5d036510e03.svg)](https://wakatime.com/badge/user/a16f794f-b91d-4818-8dfc-d768ce605ece/project/b93013d7-aceb-45a4-a283-f5d036510e03) +
[![wakatime](https://wakatime.com/badge/user/a16f794f-b91d-4818-8dfc-d768ce605ece/project/665d585c-0366-499e-8389-9f0e4e5356c4.svg)](https://wakatime.com/badge/user/a16f794f-b91d-4818-8dfc-d768ce605ece/project/665d585c-0366-499e-8389-9f0e4e5356c4)

</div>


Ce projet contient un script Python conçu pour scraper des informations sur les praticiens de santé à partir du site Doctolib.fr. Il utilise Selenium pour automatiser la navigation et l'extraction de données.

## Prérequis

Avant de lancer le script, assurez-vous d'avoir installé :
- Python 3.x
- pip (le gestionnaire de paquets Python)

## Installation

1.  Clonez ce dépôt ou téléchargez les fichiers dans un répertoire local.
2.  Ouvrez un terminal ou une invite de commande dans le répertoire du projet.
3.  Installez les dépendances Python nécessaires en exécutant :
    ```sh
    pip install selenium webdriver-manager
    ```

## Utilisation

Le script principal est [`scrap.py`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/scrap.py). Vous pouvez l'exécuter depuis la ligne de commande.

```sh
python scrap.py [OPTIONS] <query> <location>
```

### Arguments

-   `<query>` (obligatoire) : La spécialité ou le type de praticien recherché (ex: "dentiste", "dermatologue").
-   `<location>` (obligatoire) : Le lieu de recherche (ex: "Paris", "75015").

### Options

-   `--max_results <nombre>` : Nombre maximum de résultats à extraire (par défaut : 10).
    Exemple : `--max_results 20`
-   `--start_date <JJ/MM/AAAA>` : Date de début pour filtrer les disponibilités.
    Exemple : `--start_date 25/12/2023`
-   `--end_date <JJ/MM/AAAA>` : Date de fin pour filtrer les disponibilités.
    Exemple : `--end_date 31/12/2023`
-   `--insurance <type>` : Filtre par type de conventionnement.
    Choix possibles : `secteur 1`, `secteur 2`, `non conventionné`.
    Exemple : `--insurance "secteur 1"`
-   `--consultation_type <type>` : Filtre par type de consultation.
    Choix possibles : `visio`, `sur place` (par défaut : `sur place`).
    Exemple : `--consultation_type visio`
-   `--min_price <prix>` : Prix minimum pour la consultation (en €).
    Exemple : `--min_price 20`
-   `--max_price <prix>` : Prix maximum pour la consultation (en €).
    Exemple : `--max_price 100`

### Exemple de commande complète

```sh
python scrap.py --max_results 5 --insurance "secteur 1" "dentiste" "Paris"
```

## Fichiers de sortie

-   `doctolib.csv` : Ce fichier CSV est généré dans le répertoire du script et contient les données extraites des praticiens. Les colonnes incluses sont définies dans la variable `CSV_HEADERS` du script [`scrap.py`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/scrap.py):
    -   Nom complet
    -   Lien Profil
    -   Prochaine disponibilité
    -   Type de consultation
    -   Secteur d'assurance
    -   Prix estimé
    -   Rue
    -   Code postal
    -   Ville
-   Un exemple de fichier de sortie est disponible : [`exemple.csv`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/exemple.csv).

## Débogage

-   Le script utilise le module [`utils/debug_color.py`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/utils/debug_color.py) pour afficher des messages de débogage colorés dans la console, facilitant le suivi de l'exécution.
-   En cas d'erreurs spécifiques (ex: impossibilité de naviguer, absence de cartes de résultats, timeout lors de l'extraction des prix), le script peut sauvegarder le code source HTML de la page en cours dans des fichiers tels que :
    -   `debug_page_source_nav_failed.html`
    -   `debug_page_source_no_cards_final.html`
    -   `debug_profile_page_timeout_YYYYMMDD-HHMMSS.html`
    -   [`debug_page_source_general_error.html`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/debug_page_source_general_error.html)
    Ces fichiers sont utiles pour analyser la structure de la page au moment de l'erreur.

## Fichiers du projet

-   [`scrap.py`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/scrap.py) : Le script principal de scraping.
-   [`utils/debug_color.py`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/utils/debug_color.py) : Module utilitaire pour l'affichage des logs colorés.
-   [`demo.py`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/demo.py) : Un script de démonstration Selenium simple pour interagir avec Doctolib (non utilisé directement par `scrap.py`).
-   [`exemple.csv`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/exemple.csv) : Un exemple de fichier CSV de sortie.
-   [`.gitignore`](s%3A/Bureau/git/IPSSI_WebScrapSelenium/.gitignore) : Spécifie les fichiers et répertoires à ignorer par Git.
-   `debug_page_source_general_error.html` (et autres fichiers HTML de débogage) : Fichiers HTML générés pour le débogage en cas d'erreur.
