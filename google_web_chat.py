import os
import sys
import time
from playwright.sync_api import sync_playwright
from prompt_toolkit import prompt
from rich.console import Console

console = Console()

def main():
    console.print("[cyan]Starte Browser-Session für Google/Gemini...[/cyan]")
    with sync_playwright() as p:
        user_data_dir = os.path.join(os.getcwd(), "chrome_user_data")

        # Wir nutzen einen persistenten Kontext, damit Logins über Sitzungen hinweg gespeichert bleiben
        browser = p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            args=["--disable-blink-features=AutomationControlled"]
        )

        # Die Default-Page des persistenten Kontextes nutzen
        page = browser.pages[0] if browser.pages else browser.new_page()
        page.goto("https://gemini.google.com/")

        console.print("[cyan]Prüfe Login-Status...[/cyan]")
        page.wait_for_load_state("networkidle")
        time.sleep(3)

        # Überprüfen, ob wir zur Login-Seite weitergeleitet wurden
        if "accounts.google.com" in page.url:
            console.print("[yellow]Login erforderlich.[/yellow]")

            # E-Mail abfragen
            email = prompt("Bitte Google E-Mail eingeben: ")
            try:
                page.wait_for_selector('input[type="email"]', timeout=5000)
                page.fill('input[type="email"]', email)
                page.keyboard.press("Enter")
                time.sleep(3)
            except Exception as e:
                console.print("[red]Konnte E-Mail-Feld nicht finden. Bitte manuell im Browser fortfahren.[/red]")

            # Passwort abfragen
            password = prompt("Bitte Passwort eingeben: ", is_password=True)
            try:
                page.wait_for_selector('input[type="password"]', timeout=10000)
                page.fill('input[type="password"]', password)
                page.keyboard.press("Enter")
                time.sleep(5)
            except Exception as e:
                console.print("[red]Konnte Passwort-Feld nicht finden oder es gab eine Sicherheitsüberprüfung.[/red]")

            # Auf 2FA oder Weiterleitung warten
            while "accounts.google.com" in page.url:
                console.print("[yellow]Zusätzliche Bestätigung (z.B. 2FA) erforderlich![/yellow]")
                console.print("Bitte schließe den Login-Vorgang im geöffneten Browser-Fenster ab (z.B. am Smartphone bestätigen).")
                action = prompt("Drücke Enter, wenn du erfolgreich eingeloggt bist und die Gemini-Seite siehst (oder 'q' zum Abbrechen): ")
                if action.lower() == 'q':
                    browser.close()
                    sys.exit(0)
                time.sleep(2)

        console.print("[green]Erfolgreich auf Gemini zugegriffen![/green]")

        # Chat-Schleife für die Recherche
        while True:
            try:
                user_question = prompt("\nDeine Frage an Gemini (oder 'exit' zum Beenden): ")
                if user_question.lower() in ['exit', 'quit']:
                    break

                # Textbox für die Eingabe finden (Gemini nutzt div mit role="textbox" oder textarea)
                try:
                    chat_input = page.wait_for_selector('div[role="textbox"], textarea', timeout=10000)
                    chat_input.fill(user_question)
                    # Bei mehrzeiligen Eingabefeldern löst Enter manchmal nur einen Zeilenumbruch aus.
                    # Wir klicken auf den Senden-Button oder drücken Enter, abhängig vom Feld.
                    page.keyboard.press("Enter")

                    console.print("[cyan]Warte auf Antwort von Gemini...[/cyan]")

                    # Kurz warten, bis die Generierung startet
                    time.sleep(3)

                    # Wir warten, bis die neue Nachricht vollständig ist.
                    # Dies kann z.B. anhand von Ladeindikatoren oder dem Erscheinen des "Kopieren"-Buttons erkannt werden.
                    # Als Heuristik warten wir auf das message-content Element.
                    try:
                        page.wait_for_selector('message-content', state='visible', timeout=45000)
                    except:
                        pass # Manchmal heißt das Element anders, wir versuchen die Antwort dennoch zu extrahieren.

                    # Genug Zeit geben, damit der Text vollständig geladen ist
                    time.sleep(5)

                    # Antworten extrahieren
                    # Die genauen Selektoren bei Gemini können variieren, oft ist es 'message-content' oder '.model-response-text'
                    elements = page.query_selector_all('message-content, .model-response-text, .message-content')

                    if elements:
                        latest_response = elements[-1].inner_text()
                        console.print(f"\n[magenta]✦ Gemini 3.1 Pro:[/magenta]\n{latest_response}\n")
                    else:
                        console.print("[red]Konnte die Antwort nicht im Browser extrahieren. Möglicherweise haben sich die HTML-Klassen geändert.[/red]")

                except Exception as e:
                    console.print(f"[red]Fehler bei der Interaktion mit der Webseite: {e}[/red]")

            except KeyboardInterrupt:
                break

        console.print("[cyan]Schließe Browser-Session...[/cyan]")
        browser.close()

if __name__ == "__main__":
    main()
