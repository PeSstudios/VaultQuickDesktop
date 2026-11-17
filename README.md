# VaultQuick Desktop – applet Úkoly pro panel MATE

Applet na liště MATE ukazuje úkoly TaskNotes z vaultu (počty na liště, agenda po kliknutí,
odškrtnutí, rychlé přidání, formulář úkolu). Jeden proces pomocníka `vqd` (Kotlin, JVM) obsluhuje
všechny instance appletu a používá stejný kód jako Android aplikace VaultQuick.

## Instalace

Potřeba: MATE (`mate-panel`), Python 3 s GTK 3 a `MatePanelApplet-4.0`, JDK, `dconf` (jen pro zkratku).

```
./desktop/applet/install.sh --shortcut '<Mod4>t'
```

Skript sestaví `vqd` (`./gradlew :desktop:vqd:installDist`, potom `./gradlew --stop`) a nainstaluje:

- `vqd` → `~/.local/share/vaultquick-desktop/vqd/`
- applet → `~/.local/share/vaultquick-desktop/applet/`
- D-Bus služba → `~/.local/share/dbus-1/services/` (s cestou k nainstalovanému appletu)
- příkaz `vaultquick-desktop` → `~/.local/bin/`
- soubor appletu → `/usr/share/mate-panel/applets/` (jednou se `sudo`)

Je idempotentní, lze ho pustit znovu po každé změně kódu. Přepínače: `--skip-build` (bez Gradle),
`--dry-run` (jen vypíše kroky), `--shortcut` (viz níže), `--uninstall`.

Po instalaci restartujte panel: `mate-panel --replace &`.

## Přidání na lištu

Pravý klik na panel → Přidat na panel → Úkoly VaultQuick. Můžete přidat více instancí
(např. Vše, pesstudios, Constelia); každá má vlastní předvolby.

## Předvolby instance

Pravý klik na applet → Předvolby:

- projekt (název stránky) nebo Vše, popisek na liště,
- počet dní 1–14 (výchozí 7),
- úkoly bez termínu: žádné / rozpracované / všechny (výchozí: projekt všechny, Vše rozpracované),
- velikost písma (výchozí 11 pt).

Nastavení instancí je v `~/.config/vaultquick-desktop/instances.json`.

## Klávesová zkratka

`install.sh --shortcut '<Mod4>t'` založí vlastní zkratku MATE (dconf
`/org/mate/desktop/keybindings/customN/`, první volné N; pokud už zkratka se stejnou akcí existuje,
přeskočí se). Super+T pak otevře/zavře okno instance Vše. Totéž ručně:
Klávesové zkratky → Přidat, příkaz `~/.local/bin/vaultquick-desktop toggle`.

```
vaultquick-desktop toggle            # instance Vše (jinak první na liště)
vaultquick-desktop toggle pesstudios # instance s popiskem „pesstudios“
```

Příkaz volá D-Bus metodu `Toggle` na `cz.pesstudios.VaultQuickDesktop`; funguje jen, když applet
na liště běží.

## Konfigurace

`~/.config/vaultquick-desktop/config.json`:

```json
{
  "vault": "~/MujVault",
  "taskPreset": { "folder": "0 vyřídit", "fileNameTemplate": "…", "tags": ["task"] }
}
```

- `vault` – cesta k vaultu (výchozí `~/MujVault`),
- `taskPreset` – volitelné; složka, šablona názvu souboru a tagy nových úkolů (jinak se vezmou
  z nastavení TaskNotes ve vaultu).

## Odinstalace

```
./desktop/applet/install.sh --uninstall
```

Smaže nainstalované soubory (včetně `sudo rm` souboru appletu v `/usr/share/mate-panel/applets/`).
Ručně pak odeberte applet z lišty, zkratku v Klávesových zkratkách a případně
`~/.config/vaultquick-desktop/`.

## Testy

```
python3 -m unittest discover -s desktop/applet/tests     # GTK testy: VQ_GUI_TESTS=1
./gradlew :desktop:vqd:test
```
