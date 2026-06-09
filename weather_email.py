import os
import smtplib
import requests
from email.message import EmailMessage
from datetime import date, datetime

# --- Configuration : coordonnées de Cap-Rouge, Québec ---
LATITUDE = 46.75
LONGITUDE = -71.35
TIMEZONE = "America/Toronto"  # fuseau du Québec

# --- Secrets : lus depuis les variables d'environnement (jamais en clair !) ---
EMAIL_EXPEDITEUR = os.environ["EMAIL_EXPEDITEUR"]
EMAIL_MOT_DE_PASSE = os.environ["EMAIL_MOT_DE_PASSE"]
EMAIL_DESTINATAIRE = os.environ["EMAIL_DESTINATAIRE"]

# Pour afficher les jours de la semaine en français
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def obtenir_meteo():
    """Appelle l'API gratuite Open-Meteo (aucune clé requise)."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": LATITUDE,
        "longitude": LONGITUDE,
        # On ajoute "precipitation_probability_max" = la probabilité de pluie 🌧️
        "daily": (
            "temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,precipitation_probability_max"
        ),
        "timezone": TIMEZONE,
        "forecast_days": 8,  # aujourd'hui + les 7 prochains jours
    }
    reponse = requests.get(url, params=params, timeout=30)
    reponse.raise_for_status()  # déclenche une erreur si l'appel échoue
    return reponse.json()


def formater_jour(jour_iso, t_max, t_min, pluie, proba):
    """Met en forme une seule journée de météo en une ligne lisible."""
    # "jour_iso" ressemble à "2026-06-09" → on en tire le nom du jour
    d = datetime.strptime(jour_iso, "%Y-%m-%d").date()
    nom_jour = JOURS_FR[d.weekday()].capitalize()
    return (
        f"  {nom_jour} {d:%d/%m} : "
        f"min {t_min} °C / max {t_max} °C — "
        f"pluie {pluie} mm (probabilité {proba} %)"
    )


def construire_message(donnees):
    """Transforme les données brutes en texte lisible."""
    jour = donnees["daily"]
    dates = jour["time"]
    t_max = jour["temperature_2m_max"]
    t_min = jour["temperature_2m_min"]
    pluie = jour["precipitation_sum"]
    proba = jour["precipitation_probability_max"]

    # Indice 0 = aujourd'hui
    ligne_aujourdhui = formater_jour(
        dates[0], t_max[0], t_min[0], pluie[0], proba[0]
    )

    # Indices 1 à 7 = les 7 prochains jours
    lignes_semaine = "\n".join(
        formater_jour(dates[i], t_max[i], t_min[i], pluie[i], proba[i])
        for i in range(1, len(dates))
    )

    return (
        f"Bonjour Menad !\n\n"
        f"Voici la météo du jour pour Cap-Rouge, Québec "
        f"({date.today():%d/%m/%Y}) :\n\n"
        f"{ligne_aujourdhui}\n\n"
        f"🗓️  Prévisions des 7 prochains jours :\n\n"
        f"{lignes_semaine}\n\n"
        f"Bonne journée !\n"
    )


def envoyer_courriel(corps):
    """Envoie le courriel via le serveur SMTP sécurisé de Gmail."""
    message = EmailMessage()
    message["Subject"] = f"Météo Cap-Rouge — {date.today():%d/%m/%Y}"
    message["From"] = EMAIL_EXPEDITEUR
    message["To"] = EMAIL_DESTINATAIRE
    message.set_content(corps)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
        serveur.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        serveur.send_message(message)
    print("✅ Courriel envoyé avec succès !")


def main():
    donnees = obtenir_meteo()
    corps = construire_message(donnees)
    envoyer_courriel(corps)


if __name__ == "__main__":
    main()
