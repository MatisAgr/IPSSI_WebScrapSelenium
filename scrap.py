import argparse
import csv
import time
import re
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from utils.debug_color import debug_print

BASE_URL = "https://www.doctolib.fr"
CSV_HEADERS = [
    "Nom complet", "Lien Profil", "Prochaine disponibilité", "Type de consultation",
    "Secteur d'assurance", "Prix estimé", "Rue", "Code postal", "Ville"
]

def setup_driver():
    """Configure et retourne le driver Chrome."""
    debug_print("Configuration du driver Chrome...", level="info")
    service = Service(ChromeDriverManager().install())
    options = webdriver.ChromeOptions()
    driver = webdriver.Chrome(service=service, options=options)
    debug_print("Driver Chrome configuré.", level="success")
    return driver

def accept_cookies(driver, timeout=2):
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

def parse_arguments():
    """Parse et retourne les arguments de ligne de commande."""
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
    debug_print(f"Paramètres reçus : {args}", level="debug")
    return args

def search_doctolib(driver, query, location, wait):
    """Effectue une recherche sur Doctolib avec les critères donnés."""
    debug_print("Lancement de la recherche Doctolib...", level="info")
    
    # Saisie de la requête
    search_query_input_selector = "input.searchbar-input.searchbar-query-input"
    search_query_input = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, search_query_input_selector))
    )
    search_query_input.send_keys(query)
    debug_print(f"Recherche de : {query}", level="fetch")
    
    # Saisie de la localisation
    place_input_selector = "input.searchbar-input.searchbar-place-input"
    place_input = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, place_input_selector))
    )
    place_input.clear()
    place_input.send_keys(location)
    debug_print(f"Localisation : {location}", level="fetch")
    
    # Attente que la valeur soit présente dans l'input
    wait.until(
        EC.text_to_be_present_in_element_value((By.CSS_SELECTOR, place_input_selector), location)
    )
    time.sleep(1)  # Pause pour stabilisation
    debug_print("Envoi de la touche ENTREE pour la localisation.", level="debug")
    place_input.send_keys(Keys.ENTER)
    time.sleep(0.5)  # Petite pause après Entrée
    
    # Clic sur le bouton de recherche
    search_button_selector = "button.searchbar-submit-button[type='submit']"
    search_button = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, search_button_selector))
    )
    search_button.click()
    
    # Attendre que l'URL change après la recherche
    current_url_before_search_action = driver.current_url
    try:
        WebDriverWait(driver, 1).until_not(
            EC.url_to_be(current_url_before_search_action)
        )
        debug_print(f"L'URL a changé. Nouvelle URL : {driver.current_url}", level="success")
        
        # Vérification de l'URL
        query_slug = query.lower().replace(" ", "-")
        location_slug = location.lower().replace(" ", "-").split(',')[0]
        
        if not (query_slug in driver.current_url.lower() or location_slug in driver.current_url.lower()):
            debug_print(f"AVERTISSEMENT: L'URL ({driver.current_url}) a changé mais ne semble pas correspondre à une page de résultats pour '{query}' à '{location}'.", level="warning")
        
        return True
    except TimeoutException:
        debug_print(f"Timeout : L'URL n'a pas changé après le clic sur le bouton de recherche. Toujours sur {driver.current_url}", level="error")
        debug_print("La recherche n'a probablement pas été initiée correctement.", level="error")
        with open("debug_page_source_nav_failed.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        debug_print("Code source de la page (échec navigation) sauvegardé dans debug_page_source_nav_failed.html", level="info")
        return False

def find_practitioner_cards(driver):
    """Trouve et retourne les cartes de praticiens sur la page de résultats."""
    debug_print("Recherche des cartes de praticiens...", level="info")
    
    # Recherche du conteneur principal des résultats
    results_container_selector = "div[data-test-id='hcp-results']"
    results_area = None
    try:
        results_area = WebDriverWait(driver, 1).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, results_container_selector))
        )
        debug_print("Conteneur principal des résultats trouvé. Début du scrape...", level="success")
    except TimeoutException:
        debug_print(f"Conteneur principal des résultats ({results_container_selector}) non trouvé. La recherche des cartes se fera sur toute la page.", level="warning")
    
    # Contexte de recherche pour les cartes
    card_search_context = results_area if results_area else driver
    context_name = f"'{results_container_selector}'" if results_area else "la page entière"
    
    # Tentative 1: Cartes de type <article>
    practitioner_cards = []
    article_card_selector = "article[data-test^='search-result-card']"
    try:
        WebDriverWait(card_search_context, 1).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, article_card_selector))
        )
        practitioner_cards = card_search_context.find_elements(By.CSS_SELECTOR, article_card_selector)
        debug_print(f"{len(practitioner_cards)} cartes <article> trouvées avec '{article_card_selector}'.", level="info")
    except TimeoutException:
        debug_print(f"Aucune carte <article> trouvée avec '{article_card_selector}' dans {context_name} dans le délai imparti.", level="warning")
    
    # Tentative 2: Cartes de type <div> si aucune carte <article> trouvée
    if not practitioner_cards:
        div_content_card_selector = "div.dl-card-content"
        debug_print(f"Aucune carte <article> trouvée. Tentative avec le sélecteur de fallback pour cartes <div> ('{div_content_card_selector}') dans {context_name}.", level="warning")
        try:
            WebDriverWait(card_search_context, 1).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, div_content_card_selector))
            )
            practitioner_cards = card_search_context.find_elements(By.CSS_SELECTOR, div_content_card_selector)
            debug_print(f"{len(practitioner_cards)} cartes (potentiellement <div>) trouvées avec le sélecteur de fallback '{div_content_card_selector}'.", level="info")
        except TimeoutException:
            debug_print(f"Aucune carte trouvée avec le sélecteur de fallback '{div_content_card_selector}' dans {context_name}.", level="warning")
    
    debug_print(f"{len(practitioner_cards)} cartes de praticiens (final) trouvées sur la page.", level="info")
    
    # Si aucune carte trouvée, sauvegarder le code source pour débogage
    if not practitioner_cards:
        debug_print("Aucune carte de praticien trouvée avec les sélecteurs essayés. Vérifiez les sélecteurs et la structure de la page.", level="error")
        with open("debug_page_source_no_cards_final.html", "w", encoding="utf-8") as f:
            f.write(driver.page_source)
        debug_print("Code source de la page sauvegardé dans debug_page_source_no_cards_final.html", level="info")
    
    return practitioner_cards

def extract_card_data(card, card_index, driver, wait_for_results_page):
    """Extrait les données d'une carte de praticien."""
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
    
    # Déterminer le type de consultation
    try:
        is_telehealth = False
        try:
            card.find_element(By.CSS_SELECTOR, "div[data-test='telehealth-badge']")
            is_telehealth = True
        except NoSuchElementException:
            try:
                card.find_element(By.CSS_SELECTOR, "svg[data-test-id='telehealth-icon']")
                is_telehealth = True
            except NoSuchElementException:
                pass
            except Exception as e:
                debug_print(f"Erreur vérif. icône svg téléconsult. C{card_index+1}: {e}", level="warning")
        except Exception as e:
            debug_print(f"Erreur vérif. badge div téléconsult. C{card_index+1}: {e}", level="warning")
        
        data["Type de consultation"] = "visio" if is_telehealth else "Sur place"
    except Exception as e:
        debug_print(f"Erreur détermination type consultation C{card_index+1}: {e}", level="warning")
    
    
    
    
    # Extraction du nom et du lien profil
    try:
        name_h2 = card.find_element(By.CSS_SELECTOR, "h2.dl-text.dl-text-primary-110")
        data["Nom complet"] = name_h2.text.strip()
        link_element = name_h2.find_element(By.XPATH, "./ancestor::a[1]")
        profile_link = link_element.get_attribute("href")
        if profile_link:
            data["Lien Profil"] = BASE_URL + profile_link if profile_link.startswith("/") else profile_link
    except NoSuchElementException:
        debug_print(f"Nom/lien profil non trouvé C{card_index+1}", level="warning")
    except Exception as e:
        debug_print(f"Erreur Nom/Lien Profil C{card_index+1}: {e}", level="warning")
    
    
    # Extraction du prix depuis la page de profil
    if data["Lien Profil"] != "N/A" and data["Lien Profil"].startswith(BASE_URL):
        current_search_page_url = driver.current_url # Sauvegarde de l'URL actuelle
        debug_print(f"C{card_index+1}: Tentative d'extraction des prix depuis {data['Lien Profil']}", level="info")
        
        extracted_prices = extract_prices_from_profile_page(driver, data["Lien Profil"])
        data["Prix estimé"] = extracted_prices
        debug_print(f"C{card_index+1}: Prix extraits: {data['Prix estimé']}", level="info")
        
        # S'assurer que nous sommes de retour sur la page de résultats et qu'elle est chargée.
        # La fonction extract_prices_from_profile_page gère maintenant le retour à l'onglet/page d'origine.
        # Il faut s'assurer que la page de résultats est toujours dans l'état attendu.
        # Une petite attente pour la stabilisation peut être utile si des éléments sont rechargés.
        if driver.current_url != current_search_page_url:
            debug_print(f"C{card_index+1}: URL actuelle ({driver.current_url}) différente de l'URL de recherche sauvegardée ({current_search_page_url}). Tentative de retour explicite.", level="warning")
            driver.get(current_search_page_url)

        try:
            # Attendre que le conteneur des résultats soit à nouveau présent sur la page de recherche
            results_container_selector = "div[data-test-id='hcp-results']"
            wait_for_results_page.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, results_container_selector))
            )
            time.sleep(1) # Petite pause pour la stabilisation
            debug_print(f"C{card_index+1}: Retour à la page de résultats confirmé.", level="success")
        except TimeoutException:
            debug_print(f"C{card_index+1}: Timeout en attendant le conteneur de résultats après l'extraction des prix. La page de résultats n'est peut-être pas correctement rechargée.", level="error")
            # Cela pourrait causer des problèmes pour trouver la carte suivante.
    elif data["Lien Profil"] == "N/A":
        data["Prix estimé"] = "N/A (pas de lien profil)"
    else: # Lien profil non Doctolib
        data["Prix estimé"] = "N/A (lien profil externe)"
        debug_print(f"C{card_index+1}: Lien profil {data['Lien Profil']} non traité pour les prix (externe à Doctolib).", level="info")

    
    
    # Extraction de la disponibilité
    try:
        avail_container = card.find_element(By.CSS_SELECTOR, "div[data-test-id='availabilities-container']")
        availability_pills = avail_container.find_elements(By.CSS_SELECTOR, "span.dl-pill-success-020 span.dl-text")
        avail_texts = [pill.text.strip().replace("\n", " ") for pill in availability_pills]
        data["Prochaine disponibilité"] = ", ".join(avail_texts) if avail_texts else "Aucune prochainement (ou non spécifié)"
    except NoSuchElementException:
        data["Prochaine disponibilité"] = "Disponibilité non trouvée (structure attendue absente)"
    except Exception as e:
        debug_print(f"Erreur Dispo C{card_index+1}: {e}", level="warning")
        data["Prochaine disponibilité"] = "Erreur extraction dispo"
    
    # Extraction de l'adresse
    try:
        location_icon_element = card.find_element(By.CSS_SELECTOR, "svg[data-icon-name='regular/location-dot']")
        
        
        parent_div = location_icon_element.find_element(By.XPATH, "./ancestor::div[3]")
        address_paragraphs = parent_div.find_elements(
            By.XPATH, ".//div[contains(@class, 'flex-wrap')]/p"
        )        
        
        if len(address_paragraphs) >= 1:
            data["Rue"] = address_paragraphs[0].text.strip()
        
        if len(address_paragraphs) >= 2:
            cp_ville_text = address_paragraphs[1].text.strip()
            match = re.match(r"(\d{5})\s*(.*)", cp_ville_text)
            if match:
                data["Code postal"], data["Ville"] = match.group(1), match.group(2).strip()
            else:
                data["Ville"] = cp_ville_text
        elif len(address_paragraphs) == 1 and not data["Rue"]:
            cp_ville_text = address_paragraphs[0].text.strip()
            match = re.match(r"(\d{5})\s*(.*)", cp_ville_text)
            if match:
                data["Code postal"], data["Ville"] = match.group(1), match.group(2).strip()
            else:
                data["Ville"] = cp_ville_text
    except NoSuchElementException:
        debug_print(f"Bloc adresse non trouvé C{card_index+1}", level="warning")
    except Exception as e:
        debug_print(f"Erreur Adresse C{card_index+1}: {e}", level="warning")
    
    # Extraction du secteur d'assurance
    try:
        insurance_icon = card.find_element(By.CSS_SELECTOR, "svg[data-icon-name='regular/euro-sign']")
        insurance_group_div = insurance_icon.find_element(By.XPATH, "./ancestor::div[@class='gap-8 flex'][1]")
        insurance_text_p = insurance_group_div.find_element(By.CSS_SELECTOR, "div.flex.flex-wrap.gap-x-4 > p")
        data["Secteur d'assurance"] = insurance_text_p.text.strip()
    except NoSuchElementException:
        data["Secteur d'assurance"] = "N/A (info non trouvée)"
    except Exception as e:
        debug_print(f"Erreur Secteur Assurance C{card_index+1}: {e}", level="warning")
    
    return data


def extract_prices_from_profile_page(driver, profile_url):
    """Navigue vers la page de profil, extrait les tarifs et retourne une chaîne les décrivant."""
    debug_print(f"Navigation vers la page de profil : {profile_url} pour extraction des tarifs.", level="fetch")
    original_window = None
    if len(driver.window_handles) == 1: # Ouvre dans un nouvel onglet si un seul onglet est ouvert
        driver.execute_script("window.open('');")
        original_window = driver.window_handles[0]
        driver.switch_to.window(driver.window_handles[1])
    
    driver.get(profile_url)
    prices_list = []
    try:
        tarifs_section_xpath = "//div[.//h2[contains(text(), 'Tarifs') and contains(@class, 'dl-profile-card-title')]]"
        WebDriverWait(driver, 1).until(
            EC.visibility_of_element_located((By.XPATH, tarifs_section_xpath))
        )
        
        fee_elements_xpath = tarifs_section_xpath + "//li[.//span[contains(@class, 'dl-profile-fee-name')] and .//span[contains(@class, 'dl-profile-fee-tag')]]"
        
        try: # Essayer d'attendre les éléments, mais ne pas échouer si aucun n'est trouvé immédiatement (la section peut exister sans items)
            WebDriverWait(driver, 1).until(
                EC.presence_of_all_elements_located((By.XPATH, fee_elements_xpath))
            )
            fee_items = driver.find_elements(By.XPATH, fee_elements_xpath)
        except TimeoutException:
            fee_items = [] # Pas d'items de frais trouvés, mais la section "Tarifs" existe peut-être
            debug_print("Aucun élément de tarif individuel (li) trouvé dans la section tarifs après attente.", level="info")

        if not fee_items:
            # Vérifier si un message "Le praticien n'a pas encore renseigné ses tarifs" est présent
            no_tariffs_message_xpath = tarifs_section_xpath + "//p[contains(text(), 'Le praticien n') and contains(text(), 'a pas encore renseigné ses tarifs')]"
            try:
                driver.find_element(By.XPATH, no_tariffs_message_xpath)
                debug_print("Message 'Le praticien n'a pas encore renseigné ses tarifs' trouvé.", level="info")
                return "Tarifs non renseignés par le praticien"
            except NoSuchElementException:
                debug_print("Section tarifs trouvée mais vide et sans message d'absence de tarifs.", level="warning")
                return "N/A (section tarifs vide ou structure inattendue)"

        for item_idx, item in enumerate(fee_items):
            try:
                name_element = item.find_element(By.CSS_SELECTOR, "span.dl-profile-fee-name")
                tag_element = item.find_element(By.CSS_SELECTOR, "span.dl-profile-fee-tag")
                price_name = name_element.text.strip()
                price_value = tag_element.text.strip()
                prices_list.append(f"{price_name}: {price_value}")
            except NoSuchElementException:
                debug_print(f"Nom ou tag de prix manquant pour l'élément de tarif {item_idx+1}.", level="warning")
            except Exception as e_item:
                debug_print(f"Erreur lors de l'extraction d'un item de prix ({item_idx+1}): {e_item}", level="warning")
        
        if not prices_list:
            debug_print("Aucun prix n'a pu être extrait des éléments de tarif, bien que des items aient été trouvés.", level="warning")
            return "N/A (extraction des détails de prix échouée)"
            
        return ", ".join(prices_list)

    except TimeoutException:
        debug_print(f"Section tarifs non trouvée sur la page de profil {profile_url} dans le délai imparti.", level="warning")
        # Sauvegarder la page de profil pour débogage
        page_source_filename = f"debug_profile_page_timeout_{time.strftime('%Y%m%d-%H%M%S')}.html"
        try:
            with open(page_source_filename, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            debug_print(f"Code source de la page de profil sauvegardé dans : {page_source_filename}", level="info")
        except Exception as e_save:
            debug_print(f"Impossible de sauvegarder la page de profil: {e_save}", level="error")
        return "N/A (timeout section tarifs)"
    except NoSuchElementException: # Devrait être couvert par le TimeoutException sur WebDriverWait
        debug_print(f"Structure attendue pour les tarifs non trouvée sur la page de profil {profile_url}.", level="warning")
        return "N/A (structure tarifs non trouvée)"
    except Exception as e:
        debug_print(f"Erreur inattendue lors de l'extraction des prix du profil {profile_url} : {e}", level="error")
        return "N/A (erreur extraction prix)"
    finally:
        if original_window: # Si un nouvel onglet a été ouvert
            driver.close() # Ferme l'onglet du profil
            driver.switch_to.window(original_window) # Retourne à l'onglet original
            debug_print("Onglet du profil fermé, retour à l'onglet des résultats.", level="fetch")



def should_filter_card(data, args, card_index):
    """Vérifie si une carte doit être filtrée selon les critères."""
    # Vérification si toutes les données essentielles sont manquantes
    fields_to_check_for_all_na = {
        "Nom complet": ["N/A"],
        "Lien Profil": ["N/A"],
        "Prochaine disponibilité": [
            "N/A", 
            "aucune prochainement (ou non spécifié)",
            "disponibilité non trouvée (structure attendue absente)",
            "erreur extraction dispo"
        ],
        "Secteur d'assurance": ["N/A", "n/a (info non trouvée)"],
        "Rue": ["N/A"],
        "Code postal": ["N/A"],
        "Ville": ["N/A"]
    }
    
    na_count = 0
    for field, na_indicators in fields_to_check_for_all_na.items():
        current_field_value = data.get(field, "N/A")
        if isinstance(current_field_value, str) and current_field_value.lower() in [ind.lower() for ind in na_indicators]:
            na_count += 1
    
    if na_count == len(fields_to_check_for_all_na):
        debug_print(f"Carte {card_index+1} a toutes les données essentielles manquantes. Ignorée.", level="filter")
        return True
    
    # Filtrer par type de consultation
    if args.consultation_type:
        requested_consult_type = args.consultation_type.lower()
        actual_consult_type = data["Type de consultation"].lower()
        
        if not ((requested_consult_type == "sur place" and actual_consult_type == "sur place") or 
                (requested_consult_type == "visio" and actual_consult_type == "visio")):
            debug_print(f"Carte {card_index+1} filtrée (type consultation): Demandé='{args.consultation_type}', Trouvé='{data['Type de consultation']}'.", level="filter")
            return True
    
    # Filtrer par secteur d'assurance
    if args.insurance:
        requested_insurance = args.insurance.lower()
        actual_insurance = data["Secteur d'assurance"].lower()
        
        if requested_insurance not in actual_insurance:
            secteur_assurance_val = data["Secteur d'assurance"]
            debug_print(f"Carte {card_index+1} filtrée (assurance): Demandé='{args.insurance}', Trouvé='{secteur_assurance_val}'.", level="filter")
            return True
    
    return False

def process_search_results(driver, args):
    """Traite les résultats de recherche et écrit les données dans un CSV."""
    output_filename = "doctolib.csv"
    
    initial_practitioner_card_elements = find_practitioner_cards(driver)
    if not initial_practitioner_card_elements:
        debug_print("Aucune carte de praticien trouvée sur la page de résultats initiale.", level="warning")
        return 0
    
    total_cards_on_page = len(initial_practitioner_card_elements)
    cards_written_to_csv = 0
    
    # WebDriverWait pour s'assurer que la page de résultats est prête après être revenu d'une page de profil.
    # Utilise un timeout raisonnable.
    wait_for_results_page_reload = WebDriverWait(driver, 1)

    with open(output_filename, 'w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=CSV_HEADERS)
        writer.writeheader()
        debug_print(f"Fichier CSV '{output_filename}' initialisé avec les en-têtes.", level="success")
        
        # Itérer sur les indices car les références aux éléments Web (cartes) peuvent devenir "stale"
        # après avoir navigué vers une page de profil et être revenu.
        for i in range(total_cards_on_page):
            if cards_written_to_csv >= args.max_results:
                debug_print(f"Limite de {args.max_results} résultats (complets et filtrés) atteinte.", level="info")
                break
            
            print("-" * 50)
            debug_print(f"Traitement de la carte {i+1}/{total_cards_on_page}...", level="info")
            
            # Re-localiser la liste des cartes à chaque itération pour obtenir une référence fraîche
            # à l'élément de carte actuel. C'est crucial après une navigation.
            current_card_elements_on_page = find_practitioner_cards(driver)
            if i >= len(current_card_elements_on_page):
                debug_print(f"Erreur critique: Impossible de re-localiser la carte {i+1} (index {i}) après une navigation potentielle. Nombre de cartes actuelles: {len(current_card_elements_on_page)}. Arrêt du traitement des cartes pour cette page.", level="error")
                # Sauvegarder la page pour analyse
                page_source_filename = f"debug_page_source_card_reloc_fail_card_{i+1}.html"
                try:
                    with open(page_source_filename, "w", encoding="utf-8") as f:
                        f.write(driver.page_source)
                    debug_print(f"Code source de la page sauvegardé dans : {page_source_filename}", level="info")
                except Exception as e_save:
                    debug_print(f"Impossible de sauvegarder la page (échec relocalisation carte): {e_save}", level="error")
                break 
            
            current_card_element = current_card_elements_on_page[i]
            
            # Extraire les données de la carte, y compris les prix en naviguant si nécessaire
            data = extract_card_data(current_card_element, i, driver, wait_for_results_page_reload)
            
            # Vérifier si la carte doit être filtrée
            if should_filter_card(data, args, i):
                continue
            
            # Écrire dans le CSV
            writer.writerow(data)
            cards_written_to_csv += 1
            debug_print(f"Données de la carte {i+1} écrites dans le CSV: {data['Nom complet']}", level="success")
    
    if cards_written_to_csv == 0 and total_cards_on_page > 0:
        debug_print("Aucun résultat écrit dans CSV après vérif N/A et filtres (cartes trouvées initialement).", level="warning")
    elif cards_written_to_csv > 0:
        debug_print(f"{cards_written_to_csv} praticien(s) écrit(s) dans '{output_filename}'.", level="success")
    
    return cards_written_to_csv


def main():
    """Fonction principale du script."""
    debug_print("Démarrage du script de scraping Doctolib", level="info")
    
    # Analyser les arguments
    args = parse_arguments()
    
    driver = None
    try:
        # Initialiser le driver et ouvrir Doctolib
        driver = setup_driver()
        driver.get(BASE_URL)
        accept_cookies(driver)
        
        wait = WebDriverWait(driver, 1)
        
        # Effectuer la recherche
        if not search_doctolib(driver, args.query, args.location, wait):
            if driver:
                driver.quit()
            return
        
        # Traiter les résultats
        process_search_results(driver, args)
            
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