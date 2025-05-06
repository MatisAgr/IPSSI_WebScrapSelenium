import argparse
import csv
import time
import re # Ajout de re pour les expressions régulières (parsing adresse)
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
# Ajout des exceptions Selenium courantes
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from utils.debug_color import debug_print # Assurez-vous que ce chemin est correct

BASE_URL = "https://www.doctolib.fr" # Ajout de la base URL

def setup_driver():
    """Configure et retourne le driver Chrome."""
    debug_print("Configuration du driver Chrome...", level="info")
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)
    debug_print("Driver Chrome configuré.", level="success")
    return driver

def accept_cookies(driver, timeout=10):
    """Accepte les cookies sur Doctolib."""
    debug_print("Tentative d'acceptation des cookies...", level="fetch")
    try:
        cookie_button_id = "didomi-notice-agree-button"
        WebDriverWait(driver, timeout).until(
            EC.element_to_be_clickable((By.ID, cookie_button_id))
        ).click()
        debug_print("Cookies acceptés.", level="success")
    except TimeoutException:
        debug_print("Bannière de cookies non trouvée ou non cliquable dans le délai imparti.", level="warning")
    except Exception as e:
        debug_print(f"Impossible d'accepter les cookies : {e}", level="warning")

def main():
    parser = argparse.ArgumentParser(description="Scrape Doctolib pour des praticiens de santé.")
    parser.add_argument("--max_results", type=int, default=10, help="Nombre de résultats maximum à afficher.")
    parser.add_argument("--start_date", type=str, help="Date de début de disponibilité (JJ/MM/AAAA).")
    parser.add_argument("--end_date", type=str, help="Date de fin de disponibilité (JJ/MM/AAAA).")
    parser.add_argument("query", type=str, help="Requête médicale (ex: dermatologue).")
    parser.add_argument("--insurance", type=str, choices=['secteur 1', 'secteur 2', 'non conventionné'], help="Type d'assurance.")
    parser.add_argument("--consultation_type", type=str, choices=['visio', 'sur place'], default='sur place', help="Type de consultation.")
    parser.add_argument("--min_price", type=int, help="Plage de prix minimum (en €).")
    parser.add_argument("--max_price", type=int, help="Plage de prix maximum (en €).")
    parser.add_argument("location", type=str, help="Mot-clé libre pour l'adresse (ex: 75015).")

    args = parser.parse_args()

    debug_print("Démarrage du script de scraping Doctolib", level="info")
    debug_print(f"Paramètres reçus : {args}", level="debug")

    driver = None # Initialiser driver à None pour le bloc finally
    output_filename = "doctolib.csv"
    csv_headers = [
        "Nom complet", "Lien Profil", "Prochaine disponibilité", "Type de consultation",
        "Secteur d'assurance", "Prix estimé", "Rue", "Code postal", "Ville"
    ]

    try:
        driver = setup_driver()
        driver.get(BASE_URL)
        accept_cookies(driver)

        wait = WebDriverWait(driver, 5) # Délai d'attente général

        # --- Logique de recherche ---
        search_query_input_selector = "input.searchbar-input.searchbar-query-input"
        # debug_print(f"Attente de l'input de recherche: {search_query_input_selector}", level="debug")
        search_query_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, search_query_input_selector))
        )
        search_query_input.send_keys(args.query)
        debug_print(f"Recherche de : {args.query}", level="fetch")

        place_input_selector = "input.searchbar-input.searchbar-place-input"
        # debug_print(f"Attente de l'input de localisation: {place_input_selector}", level="debug")
        place_input = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, place_input_selector))
        )
        place_input.clear()
        place_input.send_keys(args.location)
        debug_print(f"Localisation : {args.location}", level="fetch")

        # debug_print(f"Attente que la valeur '{args.location}' soit présente dans l'input de localisation.", level="debug")
        wait.until(
            EC.text_to_be_present_in_element_value((By.CSS_SELECTOR, place_input_selector), args.location)
        )
        time.sleep(1) # Pause pour stabilisation et apparition des suggestions
        debug_print("Envoi de la touche ENTREE pour la localisation.", level="debug")
        place_input.send_keys(Keys.ENTER) 
        time.sleep(0.5) # Petite pause après Entrée

        search_button_selector = "button.searchbar-submit-button[type='submit']"
        # debug_print(f"Attente du bouton de recherche: {search_button_selector}", level="debug")
        search_button = wait.until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, search_button_selector))
        )
        search_button.click()
        # debug_print("Lancement de la recherche via clic sur le bouton...", level="fetch")
        
        current_url_before_search_action = driver.current_url
        # debug_print(f"URL avant attente de navigation post-recherche : {current_url_before_search_action}", level="debug")

        try:
            # Attendre que l'URL change, indiquant une navigation
            WebDriverWait(driver, 20).until_not(
                EC.url_to_be(current_url_before_search_action)
            )
            debug_print(f"L'URL a changé. Nouvelle URL : {driver.current_url}", level="success")

            query_slug = args.query.lower().replace(" ", "-")
            location_slug = args.location.lower().replace(" ", "-").split(',')[0] 

            if not (query_slug in driver.current_url.lower() or location_slug in driver.current_url.lower()):
                debug_print(f"AVERTISSEMENT: L'URL ({driver.current_url}) a changé mais ne semble pas correspondre à une page de résultats pour '{args.query}' à '{args.location}'.", level="warning")

        except TimeoutException:
            debug_print(f"Timeout : L'URL n'a pas changé après le clic sur le bouton de recherche. Toujours sur {driver.current_url}", level="error")
            debug_print("La recherche n'a probablement pas été initiée correctement.", level="error")
            with open("debug_page_source_nav_failed.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            debug_print("Code source de la page (échec navigation) sauvegardé dans debug_page_source_nav_failed.html", level="info")
            if driver:
                driver.quit()
            return 

        debug_print(f"URL finale après clic recherche et attente : {driver.current_url}", level="debug")

        results_container_selector = "div[data-test-id='hcp-results']"
        results_area = None
        try:
            # debug_print(f"Attente du conteneur principal des résultats: {results_container_selector}", level="fetch")
            # Un timeout plus court ici car la logique de recherche de cartes elle-même a des attentes.
            results_area = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, results_container_selector))
            )
            # debug_print(f"Conteneur principal des résultats ({results_container_selector}) détecté.", level="success")
            debug_print("Conteneur principal des résultats trouvé. Début du scrape...", level="success")
        except TimeoutException:
            debug_print(f"Conteneur principal des résultats ({results_container_selector}) non trouvé. La recherche des cartes se fera sur toute la page.", level="warning")
            # results_area reste None, la recherche de cartes se fera sur 'driver'

        practitioner_cards = []
        # Déterminer le contexte de recherche pour les cartes
        card_search_context = results_area if results_area else driver
        context_name = f"'{results_container_selector}'" if results_area else "la page entière"

        # Sélecteur 1: Cartes de type <article> (souvent pour la vidéo ou les nouvelles mises en page)
        # Utilise data-test^='search-result-card' pour inclure des variations comme 'search-result-card availabilities-visible'
        article_card_selector = "article[data-test^='search-result-card']"
        # debug_print(f"Recherche des cartes <article> ({article_card_selector}) dans {context_name}...", level="fetch")
        try:
            # Attendre la présence d'au moins un élément correspondant avant de les récupérer tous
            WebDriverWait(card_search_context, 15).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, article_card_selector))
            )
            practitioner_cards = card_search_context.find_elements(By.CSS_SELECTOR, article_card_selector)
            debug_print(f"{len(practitioner_cards)} cartes <article> trouvées avec '{article_card_selector}'.", level="info")
        except TimeoutException:
            debug_print(f"Aucune carte <article> trouvée avec '{article_card_selector}' dans {context_name} dans le délai imparti.", level="warning")
            practitioner_cards = [] # S'assurer que la liste est vide si rien n'est trouvé

        if not practitioner_cards:
            div_content_card_selector = "div.dl-card-content"
            debug_print(f"Aucune carte <article> trouvée. Tentative avec le sélecteur de fallback pour cartes <div> ('{div_content_card_selector}') dans {context_name}.", level="warning")
            try:
                WebDriverWait(card_search_context, 10).until(
                     EC.presence_of_all_elements_located((By.CSS_SELECTOR, div_content_card_selector))
                )
                potential_div_cards = card_search_context.find_elements(By.CSS_SELECTOR, div_content_card_selector)
                
                if not practitioner_cards: # Double vérification, devrait être vrai si on est dans ce bloc
                    practitioner_cards = potential_div_cards
                    debug_print(f"{len(practitioner_cards)} cartes (potentiellement <div>) trouvées avec le sélecteur de fallback '{div_content_card_selector}'.", level="info")




            except TimeoutException:
                debug_print(f"Aucune carte trouvée avec le sélecteur de fallback '{div_content_card_selector}' dans {context_name}.", level="warning")
                # practitioner_cards reste vide si déjà vide

        debug_print(f"{len(practitioner_cards)} cartes de praticiens (final) trouvées sur la page.", level="info")

        if not practitioner_cards:
            debug_print("Aucune carte de praticien trouvée avec les sélecteurs essayés. Vérifiez les sélecteurs et la structure de la page.", level="error")
            with open("debug_page_source_no_cards_final.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            debug_print("Code source de la page sauvegardé dans debug_page_source_no_cards_final.html", level="info")
            # Pas besoin de return ici, la boucle for ne s'exécutera pas et le script se terminera proprement.


        with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=csv_headers)
            writer.writeheader()
            debug_print(f"Fichier CSV '{output_filename}' initialisé avec les en-têtes.", level="success")

            # processed_results = 0 # Cette variable est mise à jour à la fin
            total_cards_found = len(practitioner_cards) # Renommé pour clarté, correspond à total_cards_found_on_page
            cards_written_to_csv = 0

            for i, card in enumerate(practitioner_cards):
                if cards_written_to_csv >= args.max_results:
                    debug_print(f"Limite de {args.max_results} résultats (complets et filtrés) atteinte.", level="info")
                    break
                
                print("-" * 50)
                debug_print(f"Traitement de la carte {i+1}/{total_cards_found}...", level="info")
                
                data = {
                    "Nom complet": "N/A",
                    "Lien Profil": "N/A",
                    "Prochaine disponibilité": "N/A",
                    "Type de consultation": "Sur place", 
                    "Secteur d'assurance": "N/A",
                    "Prix estimé": "N/A",
                    "Rue": "N/A",
                    "Code postal": "N/A",
                    "Ville": "N/A"
                }

                # Déterminer le type de consultation réel
                is_telehealth_actual = False
                try:
                    card.find_element(By.CSS_SELECTOR, "div[data-test='telehealth-badge']")
                    is_telehealth_actual = True
                except NoSuchElementException:
                    try:
                        card.find_element(By.CSS_SELECTOR, "svg[data-test-id='telehealth-icon']")
                        is_telehealth_actual = True
                    except NoSuchElementException:
                        pass 
                    except Exception as e_telehealth_svg:
                        debug_print(f"Erreur vérif. icône svg téléconsult. C{i+1}: {e_telehealth_svg}", level="warning")
                except Exception as e_telehealth_div:
                    debug_print(f"Erreur vérif. badge div téléconsult. C{i+1}: {e_telehealth_div}", level="warning")

                if is_telehealth_actual:
                    data["Type de consultation"] = "visio"
                else:
                    data["Type de consultation"] = "Sur place"

                # Extraction des autres données
                try:
                    name_h2 = card.find_element(By.CSS_SELECTOR, "h2.dl-text.dl-text-primary-110")
                    data["Nom complet"] = name_h2.text.strip()
                    link_element = name_h2.find_element(By.XPATH, "./ancestor::a[1]")
                    profile_link = link_element.get_attribute("href")
                    if profile_link:
                        data["Lien Profil"] = BASE_URL + profile_link if profile_link.startswith("/") else profile_link
                except NoSuchElementException:
                    debug_print(f"Nom/lien profil non trouvé C{i+1}", level="warning")
                except Exception as e_name_link:
                    debug_print(f"Erreur Nom/Lien Profil C{i+1}: {e_name_link}", level="warning")

                try:
                    avail_container = card.find_element(By.CSS_SELECTOR, "div[data-test-id='availabilities-container']")
                    availability_pills = avail_container.find_elements(By.CSS_SELECTOR, "span.dl-pill-success-020 span.dl-text")
                    avail_texts = [pill.text.strip().replace("\n", " ") for pill in availability_pills]
                    data["Prochaine disponibilité"] = ", ".join(avail_texts) if avail_texts else "Aucune prochainement (ou non spécifié)"
                except NoSuchElementException:
                    data["Prochaine disponibilité"] = "Disponibilité non trouvée (structure attendue absente)"
                except Exception as e_avail:
                    debug_print(f"Erreur Dispo C{i+1}: {e_avail}", level="warning")
                    data["Prochaine disponibilité"] = "Erreur extraction dispo"
                
                try:
                    location_icon_element = card.find_element(By.CSS_SELECTOR, "svg[data-icon-name='regular/location-dot']")
                    address_group_div = location_icon_element.find_element(By.XPATH, "./ancestor::div[@class='gap-8 flex'][1]")
                    address_text_container = address_group_div.find_element(By.CSS_SELECTOR, "div.flex.flex-wrap.gap-x-4")
                    address_lines_elements = address_text_container.find_elements(By.TAG_NAME, "p")
                    if len(address_lines_elements) >= 1: data["Rue"] = address_lines_elements[0].text.strip()
                    if len(address_lines_elements) >= 2:
                        cp_ville_text = address_lines_elements[1].text.strip()
                        match = re.match(r"(\d{5})\s*(.*)", cp_ville_text)
                        if match:
                            data["Code postal"], data["Ville"] = match.group(1), match.group(2).strip()
                        else: data["Ville"] = cp_ville_text 
                    elif len(address_lines_elements) == 1 and not data["Rue"]:
                        cp_ville_text = address_lines_elements[0].text.strip()
                        match = re.match(r"(\d{5})\s*(.*)", cp_ville_text)
                        if match: data["Code postal"], data["Ville"] = match.group(1), match.group(2).strip()
                        else: data["Ville"] = cp_ville_text
                except NoSuchElementException:
                    debug_print(f"Bloc adresse non trouvé C{i+1}", level="warning")
                except Exception as e_addr:
                    debug_print(f"Erreur Adresse C{i+1}: {e_addr}", level="warning")

                try:
                    insurance_icon = card.find_element(By.CSS_SELECTOR, "svg[data-icon-name='regular/euro-sign']")
                    insurance_group_div = insurance_icon.find_element(By.XPATH, "./ancestor::div[@class='gap-8 flex'][1]")
                    insurance_text_p = insurance_group_div.find_element(By.CSS_SELECTOR, "div.flex.flex-wrap.gap-x-4 > p")
                    data["Secteur d'assurance"] = insurance_text_p.text.strip()
                except NoSuchElementException:
                    data["Secteur d'assurance"] = "N/A (info non trouvée)"
                except Exception as e_insurance:
                    debug_print(f"Erreur Secteur Assurance C{i+1}: {e_insurance}", level="warning")

                # --- Vérification si TOUTES les données essentielles sont manquantes ---
                # On considère qu'il n'y a "aucune donnée" si tous les champs suivants sont N/A ou équivalent.
                # "Prix estimé" est toujours N/A par défaut et "Type de consultation" est toujours défini.
                
                fields_to_check_for_all_na = {
                    "Nom complet": ["N/A"],
                    "Lien Profil": ["N/A"],
                    "Prochaine disponibilité": [
                        "N/A", 
                        "aucune prochainement (ou non spécifié)",
                        "disponibilité non trouvée (structure attendue absente)",
                        "erreur extraction dispo"
                    ],
                    "Secteur d'assurance": ["N/A", "n/a (info non trouvée)"], # Inclus pour une vérification stricte de "aucune donnée"
                    "Rue": ["N/A"],
                    "Code postal": ["N/A"],
                    "Ville": ["N/A"]
                }

                na_count = 0
                for field, na_indicators in fields_to_check_for_all_na.items():
                    current_field_value = data.get(field, "N/A") # .get pour la robustesse
                    if isinstance(current_field_value, str) and current_field_value.lower() in [ind.lower() for ind in na_indicators]:
                        na_count += 1
                
                should_write_to_csv = True # Par défaut, on écrit
                if na_count == len(fields_to_check_for_all_na):
                    debug_print(f"Carte {i+1} a toutes les données essentielles manquantes. Ignorée.", level="filter")
                    should_write_to_csv = False
                    # Pas besoin de 'continue' ici, la logique de filtrage suivante et l'écriture seront sautées si should_write_to_csv est False.
                
                # Si should_write_to_csv est False à cause de la vérification N/A ci-dessus,
                # les filtres suivants ne s'appliqueront pas et la carte ne sera pas écrite.
                if not should_write_to_csv:
                    continue # Saute au prochain 'card' si toutes les données essentielles sont N/A

                # --- Filtrage basé sur les arguments (uniquement si des données ont été trouvées) ---

                # 1. Filtrer par type de consultation
                if args.consultation_type: # Ce filtre s'applique même si should_write_to_csv est déjà False (mais ne changera rien)
                    requested_consult_type_arg = args.consultation_type.lower()
                    actual_consult_type_data = data["Type de consultation"].lower()
                    
                    if not ((requested_consult_type_arg == "sur place" and actual_consult_type_data == "sur place") or \
                            (requested_consult_type_arg == "visio" and actual_consult_type_data == "visio")):
                        should_write_to_csv = False # Met à False si le filtre ne correspond pas
                        debug_print(f"Carte {i+1} filtrée (type consultation): Demandé='{args.consultation_type}', Trouvé='{data['Type de consultation']}'.", level="filter")
                
                # 2. Filtrer par secteur d'assurance (si la carte n'est pas déjà filtrée par N/A ou type de consult)
                if should_write_to_csv and args.insurance: # Ne s'exécute que si la carte est toujours candidate
                    requested_insurance_arg = args.insurance.lower() 
                    actual_insurance_data = data["Secteur d'assurance"].lower() 
                    
                    if requested_insurance_arg not in actual_insurance_data:
                        should_write_to_csv = False
                        secteur_assurance_val = data["Secteur d'assurance"]
                        debug_print(f"Carte {i+1} filtrée (assurance): Demandé='{args.insurance}', Trouvé='{secteur_assurance_val}'.", level="filter")
            
                # Écrire dans le CSV uniquement si la carte passe tous les filtres ET n'avait pas toutes les données N/A
                if should_write_to_csv:
                    writer.writerow(data)
                    cards_written_to_csv += 1
                    debug_print(f"Données de la carte {i+1} écrites dans le CSV", level="success")
                else:
                    # Ce message s'affichera si la carte a été filtrée par les arguments (type consult/assurance)
                    # ou si elle avait toutes les données N/A (le debug_print spécifique pour N/A total a déjà été émis)
                    # Pour éviter la redondance si c'était un N/A total, on pourrait ajouter une condition ici,
                    # mais le message actuel reste informatif.
                    if na_count != len(fields_to_check_for_all_na): # N'affiche ce message que si ce n'est pas un N/A total
                        debug_print(f"Carte {i+1} ignorée (rejetée par filtre d'argument).", level="info")
            
            processed_results = cards_written_to_csv 

            if processed_results == 0 and total_cards_found > 0:
                 debug_print("Aucun résultat écrit dans CSV après vérif N/A et filtres (cartes trouvées initialement).", level="warning")



    except TimeoutException:
        debug_print("Timeout: Un élément crucial n'a pas été trouvé ou n'a pas chargé à temps.", level="error")
        if driver: 
            page_source_filename = "debug_page_source_timeout.html"
            with open(page_source_filename, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            debug_print(f"Code source de la page au moment du timeout sauvegardé dans : {page_source_filename}", level="info")
    except IOError as e_io:
        debug_print(f"Erreur lors de l'ouverture ou de l'écriture du fichier CSV : {e_io}", level="error")
    except Exception as e_general:
        debug_print(f"Une erreur générale et inattendue est survenue : {e_general}", level="error")
        import traceback
        debug_print(traceback.format_exc(), level="error")
        if driver:
            page_source_filename = "debug_page_source_general_error.html"
            with open(page_source_filename, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            debug_print(f"Code source de la page au moment de l'erreur générale sauvegardé dans : {page_source_filename}", level="info")

    finally:
        print("-" * 50)
        delai_cloture = 600
        debug_print(f'Fermeture du navigateur dans {delai_cloture} secondes.')
        time.sleep(delai_cloture)
        # if driver:
        #     driver.quit()
        debug_print("Navigateur fermé. Script terminé.", level="info")

if __name__ == "__main__":
    main()