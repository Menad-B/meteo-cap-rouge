import os
import smtplib
import requests
from email.message import EmailMessage
from datetime import date, datetime

# --- Configuration : la liste des villes à inclure dans le courriel ---
# Chaque ville a un nom, ses coordonnées (latitude/longitude) et son fuseau horaire.
VILLES = [
    {
        "nom": "Cap-Rouge, Québec",
        "latitude": 46.75,
        "longitude": -71.35,
        "timezone": "America/Toronto",
    },
    {
        "nom": "Paris 19e, France",
        "latitude": 48.88,
        "longitude": 2.38,
        "timezone": "Europe/Paris",
    },
    {
        "nom": "Montesson, France",
        "latitude": 48.91,
        "longitude": 2.14,
        "timezone": "Europe/Paris",
    },
    {
        "nom": "Sahel Melbou, Algérie",
        "latitude": 36.74,
        "longitude": 5.34,
        "timezone": "Africa/Algiers",
    },
]

# --- Secrets : lus depuis les variables d'environnement (jamais en clair !) ---
EMAIL_EXPEDITEUR = os.environ["EMAIL_EXPEDITEUR"]
EMAIL_MOT_DE_PASSE = os.environ["EMAIL_MOT_DE_PASSE"]
EMAIL_DESTINATAIRE = os.environ["EMAIL_DESTINATAIRE"]

# Pour afficher les jours de la semaine en français
JOURS_FR = ["lundi", "mardi", "mercredi", "jeudi", "vendredi", "samedi", "dimanche"]


def obtenir_meteo(ville):
    """Appelle l'API gratuite Open-Meteo (aucune clé requise) pour une ville."""
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": ville["latitude"],
        "longitude": ville["longitude"],
        # Données par JOUR : min/max, pluie totale et probabilité max
        "daily": (
            "temperature_2m_max,temperature_2m_min,"
            "precipitation_sum,precipitation_probability_max"
        ),
        # Données par HEURE : température et probabilité de pluie 🌧️ pour chaque heure
        "hourly": "temperature_2m,precipitation_probability",
        "timezone": ville["timezone"],
        "forecast_days": 8,  # aujourd'hui + les 7 prochains jours
    }
    reponse = requests.get(url, params=params, timeout=30)
    reponse.raise_for_status()  # déclenche une erreur si l'appel échoue
    return reponse.json()


def formater_jour(jour_iso, t_max, t_min, pluie, proba):
    """Met en forme une seule journée de météo en une ligne lisible (résumé)."""
    # "jour_iso" ressemble à "2026-06-09" → on en tire le nom du jour
    d = datetime.strptime(jour_iso, "%Y-%m-%d").date()
    nom_jour = JOURS_FR[d.weekday()].capitalize()
    return (
        f"  {nom_jour} {d:%d/%m} : "
        f"min {t_min} °C / max {t_max} °C — "
        f"pluie {pluie} mm (probabilité max {proba} %)"
    )


def formater_heures_aujourdhui(donnees):
    """Construit le détail heure par heure POUR AUJOURD'HUI uniquement."""
    heure = donnees["hourly"]
    heures = heure["time"]            # ex: "2026-06-13T00:00"
    temperatures = heure["temperature_2m"]
    probabilites = heure["precipitation_probability"]

    aujourdhui = date.today().isoformat()  # ex: "2026-06-13"
    lignes = []
    for i, horodatage in enumerate(heures):
        # On ne garde que les heures de la journée d'aujourd'hui
        if horodatage.startswith(aujourdhui):
            hh = horodatage[11:16]  # extrait "00:00", "01:00", ...
            temp = temperatures[i]
            proba = probabilites[i]
            lignes.append(f"    {hh} : {temp} °C — pluie {proba} %")
    return "\n".join(lignes)


def construire_bloc_ville(ville):
    """Construit le bloc de texte météo pour une ville :
    - le détail heure par heure d'aujourd'hui
    - le résumé des 7 prochains jours
    """
    donnees = obtenir_meteo(ville)
    jour = donnees["daily"]
    dates = jour["time"]
    t_max = jour["temperature_2m_max"]
    t_min = jour["temperature_2m_min"]
    pluie = jour["precipitation_sum"]
    proba = jour["precipitation_probability_max"]

    # En-tête : aujourd'hui (résumé min/max)
    d0 = datetime.strptime(dates[0], "%Y-%m-%d").date()
    nom_jour0 = JOURS_FR[d0.weekday()].capitalize()
    entete_aujourdhui = (
        f"  Aujourd'hui ({nom_jour0} {d0:%d/%m}) : "
        f"min {t_min[0]} °C / max {t_max[0]} °C"
    )

    # Détail heure par heure d'aujourd'hui
    detail_heures = formater_heures_aujourdhui(donnees)

    # Résumé des 7 prochains jours
    lignes_semaine = "\n".join(
        formater_jour(dates[i], t_max[i], t_min[i], pluie[i], proba[i])
        for i in range(1, len(dates))
    )

    return (
        f"📍 {ville['nom']}\n"
        f"{entete_aujourdhui}\n\n"
        f"  ⏰ Détail heure par heure (aujourd'hui) :\n"
        f"{detail_heures}\n\n"
        f"  🗓️  Prévisions des 7 prochains jours :\n"
        f"{lignes_semaine}\n"
    )


def construire_message():
    """Assemble le courriel complet avec toutes les villes."""
    blocs = "\n".join(construire_bloc_ville(ville) for ville in VILLES)
    return (
        f"Bonjour Menad !\n\n"
        f"Voici la météo du jour et des 7 prochains jours "
        f"({date.today():%d/%m/%Y}) :\n\n"
        f"{blocs}\n"
        f"Bonne journée !\n"
    )


def envoyer_courriel(corps):
    """Envoie le courriel via le serveur SMTP sécurisé de Gmail."""
    # EMAIL_DESTINATAIRE peut contenir plusieurs adresses séparées par des virgules.
    destinataires = [
        adresse.strip()
        for adresse in EMAIL_DESTINATAIRE.split(",")
        if adresse.strip()
    ]

    message = EmailMessage()
    message["Subject"] = f"Météo (4 villes) — {date.today():%d/%m/%Y}"
    message["From"] = EMAIL_EXPEDITEUR
    message["To"] = ", ".join(destinataires)
    message.set_content(corps)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as serveur:
        serveur.login(EMAIL_EXPEDITEUR, EMAIL_MOT_DE_PASSE)
        serveur.send_message(message)
    print(f"✅ Courriel envoyé à {len(destinataires)} destinataire(s) !")


def main():
    corps = construire_message()
    envoyer_courriel(corps)


if __name__ == "__main__":
    main()
