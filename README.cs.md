# VaultQuick Desktop – úkoly z Obsidianu na liště MATE

[English](README.md) | **Česky**

Applet pro panel prostředí **MATE** (Linux Mint MATE, Ubuntu MATE…), který ukazuje úkoly
z vašeho vaultu [Obsidian](https://obsidian.md) spravované pluginem
[TaskNotes](https://github.com/callumalpass/tasknotes).

![Okno appletu s agendou na několik dní](docs/img/okno.png)

- **Na liště** počet dnešních a zpožděných úkolů (volitelně s ikonou projektu).
- **Po kliknutí** agenda: zpožděné, dnes a dalších několik dní, pozdější termíny a úkoly
  bez termínu.
- **Odškrtnutí** úkolu přímo v okně, **＋** pro rychlé přidání úkolu na zvolený den,
  formulář pro úpravu úkolu, otevření poznámky v Obsidianu.
- **Více instancí** na liště – např. jedna pro všechny úkoly a další pro jednotlivé projekty.
- **Klávesová zkratka** (např. Super+T) pro otevření okna.

Applet pracuje přímo se soubory ve vaultu, Obsidian nemusí běžet. Rozhraní je česky nebo anglicky
podle jazyka systému (vynutit jde proměnnou `VQ_LANG=cs` / `VQ_LANG=en`).

## Požadavky

- Pracovní prostředí **MATE** s panelem `mate-panel` (v GNOME, Cinnamonu, KDE apod. applet nefunguje).
- Vault Obsidianu s pluginem **TaskNotes** – každý úkol je samostatná poznámka (`.md`)
  s vlastnostmi jako `status`, `due`, `scheduled`, `projects`. Applet čte nastavení TaskNotes
  z `.obsidian/plugins/tasknotes/data.json` ve vaultu.
- Linux Mint, Ubuntu nebo Debian (pro instalaci z balíčku `.deb`).

## Instalace

### 1. Stažení a instalace balíčku

Stáhněte `vaultquick-desktop_…_all.deb` z
[posledního vydání](https://github.com/PeSstudios/VaultQuickDesktop/releases/latest)
a otevřete ho dvojklikem (nainstaluje se i s Javou a dalšími potřebnými balíčky). Nebo v terminálu:

```
sudo apt install ./vaultquick-desktop_1.2.0_all.deb
```

### 2. Přidání na lištu

Odhlaste se a znovu přihlaste (nebo restartujte panel příkazem `mate-panel --replace &`).
Pak pravý klik na panel → **Přidat na panel…** → **Úkoly VaultQuick**.

### 3. Výběr vaultu

Klikněte na applet. Při prvním spuštění ukáže **Vault nenalezen** a tlačítko **Vybrat vault…** –
vyberte složku svého vaultu Obsidianu. Později jde vault změnit přes pravý klik na applet →
**Vybrat vault…**.

### 4. Klávesová zkratka (volitelné)

Ovládací centrum → Klávesové zkratky → **Přidat**, název např. „Úkoly“, příkaz
`vaultquick-desktop toggle`, a přiřaďte klávesy (např. Super+T).

### Instalace ze zdrojových kódů

Bez balíčku, např. na jiné distribuci s MATE:

```
sudo apt install git python3-gi gir1.2-gtk-3.0 gir1.2-matepanelapplet-4.0 default-jdk
git clone https://github.com/PeSstudios/VaultQuickDesktop.git
cd VaultQuickDesktop
./applet/install.sh --shortcut '<Mod4>t'
mate-panel --replace &
```

`install.sh` sestaví pomocníka (poprvé to trvá několik minut, Gradle si stáhne knihovny),
nainstaluje vše do domovského adresáře a jednou požádá o `sudo` (soubor appletu do
`/usr/share/mate-panel/applets/`). `--shortcut` rovnou založí klávesovou zkratku.

## Použití

- **Klik** na applet otevře okno s agendou, další klik (nebo Esc) ho zavře.
- **Zaškrtávací pole** úkol dokončí, klik na název úkolu otevře formulář, **＋** u dne přidá úkol.
- **Pravý klik** na applet → **Předvolby** (nastavení této instance), **Obnovit**,
  **Otevřít v Obsidianu** nebo **Vybrat vault…**.
- Můžete přidat více instancí (např. Vše, Práce, Dům) – každá má vlastní předvolby.

### Předvolby instance

- projekt (název stránky) nebo Vše, popisek na liště,
- počet dní 0–14 (výchozí 7); **0** = okno bez úkolů (ani zpožděné, pozdější a bez termínu),
  jen odkazy do průzkumníku a Obsidianu,
- úkoly bez termínu: žádné / rozpracované / všechny (výchozí: projekt všechny, Vše rozpracované),
- velikost písma (výchozí 11 pt),
- ikona na liště: **Podle projektu** (výchozí – obrázek z vlastnosti `ikona:` stránky projektu ve
  formátu pluginu Image Icons, např. `ikona: "[[g4.png]]"`; instance Vše a projekty bez `ikona:`
  ikonu nemají), **Vybrat obrázek…** (libovolný obrázek z vaultu – png, jpg, jpeg, gif, webp, svg,
  bmp; soubor mimo vault se neuloží) nebo **Bez ikony**. Obrázek se neořezává, jen se zmenší na
  výšku lišty se zachováním poměru stran,
- **Zobrazit i popisek** (výchozí ne): s ikonou jsou na liště jen počty a popisek je v tooltipu;
  bez ikony se popisek ukazuje vždy,
- **Otevřít v průzkumníku** a **Otevřít v Obsidianu**: zaškrtnuté řádky se ukazují pod záhlavím
  okna (výchozí oba). Při počtu dní 0 a jediném zaškrtnutém řádku klik na applet otevře cíl
  rovnou, bez okna. Cíl je dán projektem: průzkumník otevře složku se stránkou projektu
  (u Vše kořen vaultu), Obsidian stránku projektu (u Vše stránku TaskNotes).

Ikona ze stránky projektu se zjišťuje při startu appletu, po uložení Předvoleb a při ručním
Obnovit – po změně `ikona:` v Obsidianu stačí Obnovit.

V okně je tolik dní, kolik je v Předvolbách; úkoly s pozdějším termínem jsou ve sbalitelné sekci
**Další dny** (každý jednou, s nejbližším termínem a datem; opakované podle `scheduled`).
Sekce **Bez termínu** má také ＋ – zapíše úkol bez termínu do projektu instance.

Nastavení instancí je v `~/.config/vaultquick-desktop/instances.json`.

### Klávesová zkratka

`install.sh --shortcut '<Mod4>t'` založí vlastní zkratku MATE (dconf
`/org/mate/desktop/keybindings/customN/`, první volné N; pokud už zkratka se stejnou akcí existuje,
přeskočí se). Super+T pak otevře/zavře okno instance Vše. Totéž ručně:
Ovládací centrum → Klávesové zkratky → Přidat, příkaz `~/.local/bin/vaultquick-desktop toggle`.

```
vaultquick-desktop toggle          # instance Vše (jinak první na liště)
vaultquick-desktop toggle Práce    # instance s popiskem „Práce“
```

Funguje jen, když applet na liště běží.

## Konfigurace

`~/.config/vaultquick-desktop/config.json`:

```json
{
  "vault": "~/MujVault",
  "taskPreset": { "folder": "Úkoly", "fileNameTemplate": "…", "tags": ["task"] }
}
```

- `vault` – cesta k vaultu (nastaví ji **Vybrat vault…**; výchozí `~/MujVault`),
- `taskPreset` – volitelné; složka, šablona názvu souboru a tagy nových úkolů (jinak se vezmou
  z nastavení TaskNotes ve vaultu).

## Aktualizace

Stáhněte a nainstalujte novější `.deb` stejně jako poprvé, pak se odhlaste a přihlaste
(nebo `mate-panel --replace &`). Při instalaci ze zdrojů: `git pull`, `./applet/install.sh`.

## Odinstalace

```
sudo apt remove vaultquick-desktop
```

Při instalaci ze zdrojů `./applet/install.sh --uninstall`. Ručně pak odeberte applet z lišty,
klávesovou zkratku a případně nastavení v `~/.config/vaultquick-desktop/`.

## Pro vývojáře

Applet je v Pythonu (GTK 3, `applet/`). Data z vaultu mu dodává pomocník `vqd` (Kotlin, JVM,
`vqd/`) – jeden proces pro všechny instance appletu, komunikace řádky JSON přes stdin/stdout.

`install.sh` sestaví `vqd` (`./gradlew :vqd:installDist`, potom `./gradlew --stop`) a nainstaluje:

- `vqd` → `~/.local/share/vaultquick-desktop/vqd/`
- applet → `~/.local/share/vaultquick-desktop/applet/`
- D-Bus služba → `~/.local/share/dbus-1/services/` (s cestou k nainstalovanému appletu)
- příkaz `vaultquick-desktop` → `~/.local/bin/`
- soubor appletu → `/usr/share/mate-panel/applets/` (sudo)

Skript je idempotentní. Přepínače: `--skip-build` (bez Gradle), `--dry-run` (jen vypíše kroky),
`--shortcut`, `--uninstall`. Zkratka volá D-Bus metodu `Toggle` na `cz.pesstudios.VaultQuickDesktop`.

Balíček `.deb` (do `dist/`):

```
packaging/build-deb.sh 1.2.0
```

Testy:

```
python3 -m unittest discover -s applet/tests     # GTK testy: VQ_GUI_TESTS=1
./gradlew :vqd:test
```

Jádro pomocníka `vqd` (`vqd/src/main/kotlin/…/core/**`, `vault/`, `reminders/`) je převzaté
z Android aplikace VaultQuick a kompiluje se jako obyčejné JVM – nesmí importovat `android.*`
ani `androidx.*`.

## Licence

MIT – viz [LICENSE](LICENSE).
