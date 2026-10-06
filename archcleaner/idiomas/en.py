"""English translations. Keys are the Spanish texts exactly as they appear in the code (tr("...")).

Placeholders like {n} or {ruta} must stay the same; tests/test_i18n.py checks that every
tr("...") in the code has an entry here and that the placeholders match.
"""

TEXTOS: dict[str, str] = {
    # ── modelo, estado, análisis ──
    "Basura segura": "Safe junk",
    "Para revisar": "Review",
    "Solo informativo": "Info only",
    "se borra (se regenera solo)": "deleted (regenerates by itself)",
    "se vacía el contenido": "contents are emptied",
    "va a la papelera (recuperable)": "goes to the trash (recoverable)",
    "recién": "just now",
    "hace {n} min": "{n} min ago",
    "hace {n} h": "{n} h ago",
    "ayer": "yesterday",
    "hace {n} días": "{n} days ago",
    "Escaneando {raiz}  ({i} de {n})": "Scanning {raiz}  ({i} of {n})",
    "Escaneando {raiz}  ·  {n:,} carpetas  ·  {d}": "Scanning {raiz}  ·  {n:,} folders  ·  {d}",
    "{n:,} carpetas  ·  {d}": "{n:,} folders  ·  {d}",
    "revisando: {nombre}": "checking: {nombre}",
    "Buscando qué sobra": "Looking for junk",
    "Falló el detector «{nombre}»:": "The «{nombre}» detector failed:",
    # nombres de los detectores
    "Sistema": "System",
    "Pacman": "Pacman",
    "AUR": "AUR",
    "Flatpak": "Flatpak",
    "Steam": "Steam",
    "Desarrollo": "Development",
    "Home": "Home",
    "Archivos gigantes": "Huge files",

    # ── acciones ──
    "salteado: cerrá {programas} y volvé a intentar": "skipped: close {programas} and try again",
    "{n} elementos a la papelera": "{n} items moved to the trash",
    "{n} elementos borrados": "{n} items deleted",
    " · {n} ya no estaban": " · {n} were already gone",
    "gio trash falló": "gio trash failed",
    "bloqueado por seguridad: {ruta}: {motivo}": "blocked for safety: {ruta}: {motivo}",
    "«{comando}…» terminó con error ({codigo})": "«{comando}…» failed ({codigo})",
    "ya no estaba (se borró antes)": "already gone (deleted earlier)",
    "hecho": "done",
    "(ya no estaba)": "(already gone)",

    # ── seguridad ──
    "ya no existe": "no longer exists",
    "{motivo} (la ruta pasa por un enlace a {destino})": "{motivo} (the path goes through a link to {destino})",
    "carpeta del sistema protegida": "protected system folder",
    "son datos o código del propio ArchCleaner": "it's ArchCleaner's own data or code",
    "carpeta personal protegida (se puede borrar lo de adentro, no la carpeta)":
        "protected personal folder (what's inside can be deleted, not the folder itself)",
    "es un punto de montaje (un disco entero)": "it's a mount point (a whole drive)",
    "fuera de las zonas donde ArchCleaner puede borrar": "outside the areas where ArchCleaner may delete",
    "módulos del kernel que estás usando": "modules of the kernel you're running",
    "archivo vital del sistema": "vital system file",
    "adentro hay un disco montado ({ruta})": "there is a mounted drive inside ({ruta})",
    "pertenece a un paquete instalado (lo maneja pacman)": "belongs to an installed package (pacman handles it)",
    "adentro hay un archivo de un paquete instalado ({archivo})":
        "it contains a file from an installed package ({archivo})",
    "tiene más de {n} archivos: revisalo a mano": "it has more than {n} files: check it by hand",

    # ── timeshift ──
    "manual": "manual",
    "al arrancar": "on boot",
    "cada hora": "hourly",
    "diaria": "daily",
    "semanal": "weekly",
    "mensual": "monthly",

    # ── detectores: sistema ──
    "Snapshots de Timeshift de más de {n} días": "Timeshift snapshots older than {n} days",
    "Las snapshots manuales Timeshift no las borra nunca solo, así que se acumulan. El peso es lo que se libera de verdad: solo los archivos que no comparte con otras snapshots. La más reciente ({nombre}) se conserva siempre.":
        "Timeshift never deletes manual snapshots by itself, so they pile up. The size shown is what you "
        "really free: only the files not shared with other snapshots. The most recent one ({nombre}) is always kept.",
    "{nombre}  ({tipo}, hace {dias} días{nota})": "{nombre}  ({tipo}, {dias} days ago{nota})",
    "timeshift --delete de las snapshots elegidas": "timeshift --delete for the selected snapshots",
    "Logs viejos del sistema (journald)": "Old system logs (journald)",
    "Los registros del sistema ocupan {usado}. Se recortan a los {objetivo} más recientes: alcanza de sobra para diagnosticar problemas.":
        "System logs take {usado}. They are trimmed to the most recent {objetivo}: more than enough to "
        "troubleshoot problems.",
    "Coredumps (programas que se colgaron)": "Coredumps (programs that crashed)",
    "{programa} ({n} cuelgues)": "{programa} ({n} crashes)",
    "Cuando un programa se cuelga, systemd guarda una 'foto' de su memoria para depurarlo. Hay {n}. No sirven para nada salvo que estés reportando un bug. Si un programa aparece muchas veces, es una pista de que algo anda mal con él.":
        "When a program crashes, systemd saves a 'snapshot' of its memory for debugging. There are {n}. "
        "They're useless unless you're reporting a bug. If a program shows up many times, that's a hint "
        "something is wrong with it.",
    "rm de los {n} coredumps en {carpeta}": "rm of the {n} coredumps in {carpeta}",
    "Módulos de un kernel que ya no está ({version})": "Modules of a kernel that's gone ({version})",
    "Quedaron de un kernel desinstalado o actualizado (a veces los deja DKMS). No es el kernel que estás usando ahora.":
        "Left over from an uninstalled or updated kernel (DKMS sometimes leaves them). It's not the kernel "
        "you're running now.",
    "Hay {n} snapshot(s): {nombres}.": "There are {n} snapshot(s): {nombres}.",
    "Ahora mismo no hay snapshots guardadas.": "There are no saved snapshots right now.",
    " Cada snapshot nueva ocupa unos {peso} (las siguientes, solo lo que cambió).":
        " Each new snapshot takes about {peso} (later ones, only what changed).",
    " OJO: se guardan en el MISMO disco del sistema. Si ese disco falla, perdés el sistema y las snapshots juntos.":
        " CAREFUL: they're stored on the SAME drive as the system. If that drive fails, you lose the system "
        "and the snapshots together.",
    " Esto se maneja desde Timeshift, no desde acá.": " This is managed from Timeshift, not from here.",
    "Snapshots de Timeshift": "Timeshift snapshots",

    # ── detectores: pacman, AUR, Flatpak ──
    "No está instalado pacman-contrib (paccache): no se puede analizar la caché de pacman.":
        "pacman-contrib (paccache) is not installed: the pacman cache can't be analyzed.",
    "Versiones viejas en la caché de paquetes": "Old versions in the package cache",
    "Pacman guarda cada versión que descargó (la caché pesa {total} en total). Se conservan las 2 últimas de cada paquete por si una actualización sale mal y necesitás volver atrás; se borran {n} versiones más viejas.":
        "Pacman keeps every version it downloaded (the cache takes {total} in total). The last 2 of each "
        "package are kept in case an update goes wrong and you need to roll back; {n} older versions are deleted.",
    "Caché de paquetes que ya desinstalaste": "Cache of packages you already uninstalled",
    "{n} archivos de paquetes que ya no tenés instalados.": "{n} files of packages you no longer have installed.",
    "Paquetes huérfanos": "Orphaned packages",
    "Se instalaron como dependencia de algo que ya desinstalaste y nadie más los usa. Ojo: si alguno lo usás vos directamente (por ejemplo un compilador), quedátelo.":
        "They were installed as a dependency of something you already removed and nothing else uses them. "
        "Careful: if you use one of them directly (a compiler, for example), keep it.",
    "pacman te va a mostrar la lista y pedir confirmación.": "pacman will show you the list and ask for confirmation.",
    "Paquetes de depuración (-debug)": "Debug packages (-debug)",
    "Símbolos para depurar programas compilados del AUR. Solo sirven si vas a investigar un cuelgue con gdb. Se crean porque /etc/makepkg.conf tiene la opción «debug»: para que no se generen más, creá ~/.config/pacman/makepkg.conf con la línea  OPTIONS+=(!debug)":
        "Debug symbols for programs built from the AUR. Only useful if you're going to investigate a crash "
        "with gdb. They're created because /etc/makepkg.conf has the «debug» option: to stop generating "
        "them, create ~/.config/pacman/makepkg.conf with the line  OPTIONS+=(!debug)",
    "Configs .pacnew / .pacsave pendientes": "Pending .pacnew / .pacsave configs",
    ".pacsave = config de un programa desinstalado que pacman guardó por las dudas (resto). .pacnew = config nueva que trajo una actualización y no se aplicó. No ocupan casi nada, pero conviene revisarlas (con `pacdiff`, de pacman-contrib).":
        ".pacsave = config of an uninstalled program that pacman kept just in case (a leftover). .pacnew = "
        "new config brought by an update that wasn't applied. They take almost no space, but you should "
        "review them (with `pacdiff`, from pacman-contrib).",
    "Caché de compilación de {helper}": "{helper} build cache",
    "{helper} guarda acá el código y los paquetes que compiló del AUR. Se vuelve a descargar si actualizás o reinstalás algo.":
        "{helper} keeps here the source code and packages it built from the AUR. It's downloaded again if "
        "you update or reinstall something.",
    "Datos de apps Flatpak que ya no están instaladas": "Data of Flatpak apps that are no longer installed",
    "Al desinstalar un Flatpak sin --delete-data, sus datos quedan en ~/.var/app. Puede haber partidas guardadas o configs que quieras conservar: mirá antes de borrar.":
        "When a Flatpak is uninstalled without --delete-data, its data stays in ~/.var/app. There may be "
        "saved games or configs you want to keep: take a look before deleting.",
    "Runtimes de Flatpak que ninguna app usa": "Flatpak runtimes no app uses",
    "Son las 'bases' que necesitan las apps Flatpak. Estas no las usa ninguna app instalada.":
        "These are the 'bases' Flatpak apps need. None of your installed apps use these ones.",

    # ── detectores: Steam ──
    "Shader cache de juegos desinstalados": "Shader cache of uninstalled games",
    "Shaders precompilados de juegos que ya no tenés. Si reinstalás el juego, se regeneran.":
        "Precompiled shaders of games you no longer have. If you reinstall the game, they're regenerated.",
    "Contenido de Workshop de juegos desinstalados": "Workshop content of uninstalled games",
    "Mods/contenido de Workshop de juegos que ya no están instalados.":
        "Mods/Workshop content of games that are no longer installed.",
    "Descargas a medias": "Unfinished downloads",
    "Temporales de Steam": "Steam temporary files",
    "Descargas a medias de Workshop": "Unfinished Workshop downloads",
    "Temporales de Workshop": "Workshop temporary files",
    "juego: {nombre}": "game: {nombre}",
    "{que} de {nombre}": "{que} of {nombre}",
    "Juegos instalados en {lib}": "Games installed in {lib}",
    "Lo que pesa cada juego (y herramientas como Proton). Si alguno no lo jugás más, desinstalalo desde Steam.":
        "The size of each game (and tools like Proton). If you don't play one anymore, uninstall it from Steam.",
    "resto de juego desinstalado": "leftover of an uninstalled game",
    "Carpetas de juegos que Steam ya no reconoce ({lib})": "Game folders Steam no longer recognizes ({lib})",
    "Están en steamapps/common pero ningún juego instalado las usa: suelen quedar al desinstalar (mods, configs, archivos que agregaste vos). Puede haber partidas guardadas.":
        "They're in steamapps/common but no installed game uses them: they usually remain after "
        "uninstalling (mods, configs, files you added yourself). There may be saved games.",
    "de un juego no-Steam (acceso directo)": "from a non-Steam game (shortcut)",
    "  ⚠ puede tener partidas guardadas": "  ⚠ may contain saved games",
    "Prefijos de Proton de juegos desinstalados ({lib})": "Proton prefixes of uninstalled games ({lib})",
    "Cada juego de Windows tiene su propio 'Windows falso' (compatdata). Steam no lo borra al desinstalar porque ahí adentro suelen estar las PARTIDAS GUARDADAS. Si no vas a volver a jugar (o el juego guarda en la nube), se puede borrar.":
        "Each Windows game has its own 'fake Windows' (compatdata). Steam doesn't delete it on uninstall "
        "because SAVED GAMES usually live inside. If you won't play again (or the game saves to the "
        "cloud), it can be deleted.",
    "workshop: {nombre}": "workshop: {nombre}",
    "Workshop de {juego}": "{juego} Workshop",
    "Contenido de Workshop al que estás suscripto ({n} ítems). Si lo borrás a mano, Steam lo vuelve a bajar: la forma correcta es desuscribirte en Steam de lo que no uses. Entre paréntesis va el ID: steamcommunity.com/sharedfiles/filedetails/?id=ID te lleva a su página.":
        "Workshop content you're subscribed to ({n} items). If you delete it by hand, Steam downloads it "
        "again: the right way is to unsubscribe in Steam from what you don't use. The ID is in "
        "parentheses: steamcommunity.com/sharedfiles/filedetails/?id=ID takes you to its page.",
    "Archivos temporales de Steam. Si tenés una descarga pausada que querés retomar, esperá a que termine; si no, se pueden borrar (con Steam cerrado).":
        "Steam temporary files. If you have a paused download you want to resume, wait for it to finish; "
        "otherwise they can be deleted (with Steam closed).",
    "Proton que ningún juego de Steam usa": "Proton no Steam game uses",
    "Versiones de Proton que ningún juego de Steam usa": "Proton versions no Steam game uses",
    "Están en compatibilitytools.d pero no hay ningún juego de Steam configurado para usarlas. OJO: launchers como Heroic, Lutris o umu pueden estar usándolas por fuera de Steam.":
        "They're in compatibilitytools.d but no Steam game is set to use them. CAREFUL: launchers like "
        "Heroic, Lutris or umu may be using them outside Steam.",

    # ── detectores: desarrollo ──
    "pnpm (store)": "pnpm (store)",
    "go (compilación)": "go (build)",
    "go (módulos)": "go (modules)",
    "Cachés de herramientas de programación": "Programming tool caches",
    "Paquetes descargados por npm, pip, go, etc. Se vuelven a bajar solos cuando los necesitás (la próxima instalación tarda un poco más).":
        "Packages downloaded by npm, pip, go, etc. They're downloaded again by themselves when needed (the "
        "next install takes a bit longer).",
    "sin tocar hace {n} días": "untouched for {n} days",
    "proyecto activo": "active project",
    "Dependencias de proyectos (node_modules / venv)": "Project dependencies (node_modules / venv)",
    "Librerías instaladas por proyecto. Se regeneran con `npm install` o `pip install -r ...`. Las de proyectos que no tocás hace rato son buenas candidatas.":
        "Libraries installed per project. They're regenerated with `npm install` or `pip install -r ...`. "
        "The ones of projects you haven't touched in a while are good candidates.",

    # ── detectores: home ──
    "modelos de IA descargados (pueden ser varios GB)": "downloaded AI models (can be several GB)",
    "modelos de PyTorch descargados": "downloaded PyTorch models",
    "modelos de Whisper descargados": "downloaded Whisper models",
    "navegadores que instaló Playwright": "browsers installed by Playwright",
    "incluye los entornos virtuales de tus proyectos de Poetry": "includes the virtual environments of your Poetry projects",
    "índices de los IDE de JetBrains (reindexar tarda)": "JetBrains IDE indexes (reindexing takes time)",
    "modelos de LM Studio": "LM Studio models",
    "Cachés que cuesta regenerar (~/.cache)": "Caches that are costly to regenerate (~/.cache)",
    "Técnicamente son caché, pero volver a tenerlas cuesta: descargas grandes o cosas que dejan de andar hasta reinstalarlas. Borralas solo si sabés que no las vas a usar.":
        "Technically they're cache, but getting them back is costly: big downloads, or things that stop "
        "working until reinstalled. Delete them only if you know you won't use them.",
    "Caché de programas (~/.cache)": "Program cache (~/.cache)",
    "Archivos temporales que los programas regeneran solos (miniaturas, caché del navegador, etc.). Conviene cerrar los programas antes de limpiar. Lo único que notás es que la primera vez algunas cosas cargan un poco más lento.":
        "Temporary files programs regenerate by themselves (thumbnails, browser cache, etc.). Better close "
        "programs before cleaning. The only thing you'll notice is that some things load a bit slower the first time.",
    "Cerrá el navegador y los programas cuya caché vayas a borrar.":
        "Close the browser and the programs whose cache you're going to delete.",
    "Papelera": "Trash",
    "Cosas que ya mandaste a la papelera (también lo que mandó ArchCleaner). Vaciarla es definitivo y son archivos tuyos, por eso no viene tildada: echale un vistazo antes.":
        "Things you already sent to the trash (including what ArchCleaner sent). Emptying it is permanent "
        "and these are your files, so it's not pre-selected: take a look first.",
    "Descargas de hace más de {n} días": "Downloads older than {n} days",
    "Instaladores, ISOs, comprimidos... cosas que bajaste hace rato y probablemente ya usaste.":
        "Installers, ISOs, archives... things you downloaded a while ago and probably already used.",
    "Posibles restos de programas que ya no están": "Possible leftovers of programs that are gone",
    "Carpetas de configuración/datos cuyo nombre no coincide con nada instalado. Es una suposición por nombre: puede ser de un AppImage, un programa portable o algo que usás. Revisá una por una.":
        "Config/data folders whose name doesn't match anything installed. It's a guess based on the name: "
        "it may belong to an AppImage, a portable program or something you use. Check them one by one.",

    # ── detectores: archivos grandes ──
    "Archivos": "Files",
    "Instaladores de juegos/programas": "Game/program installers",
    "Carpetas con un instalador (setup.exe) y archivos enormes al lado. Si el juego o programa ya está instalado y funciona, el instalador sobra (salvo que lo quieras para reinstalar).":
        "Folders with an installer (setup.exe) and huge files next to it. If the game or program is already "
        "installed and works, the installer is no longer needed (unless you want it to reinstall).",
    "Juegos instalados por fuera de Steam": "Games installed outside Steam",
    "No es basura: son juegos instalados a mano (Hydra, repacks, GOG...). Se muestran porque pesan mucho: si ya no jugás alguno, borrar su carpeta libera todo eso. Ojo: con Proton/Wine las partidas suelen guardarse en el prefijo, no acá, así que borrar el juego no las borra.":
        "Not junk: these are games installed by hand (Hydra, repacks, GOG...). They're shown because they're "
        "big: if you don't play one anymore, deleting its folder frees all that. Note: with Proton/Wine, "
        "saves are usually stored in the prefix, not here, so deleting the game doesn't delete them.",
    "Archivos gigantes (más de 1 GB)": "Huge files (over 1 GB)",
    "No se sabe si sobran: pueden ser juegos instalados por fuera de Steam, máquinas virtuales, videos o ISOs. Fijate si te conviene quedártelos.":
        "It's unknown whether they're needed: they may be games installed outside Steam, virtual machines, "
        "videos or ISOs. Decide whether you want to keep them.",

    # ── línea de comandos ──
    "Analizador y limpiador de disco para Arch Linux. Por defecto no borra nada.":
        "Disk analyzer and cleaner for Arch Linux. It deletes nothing by default.",
    "idioma de la interfaz (por defecto, el del sistema)": "interface language (default: the system's)",
    "informe de qué ocupa espacio y qué se puede limpiar (solo lectura)":
        "report of what takes up space and what can be cleaned (read-only)",
    "no recorre los discos enteros: solo las fuentes de basura conocidas":
        "don't scan whole drives: only known junk sources",
    "no guarda el informe en ~/.local/state/archcleaner": "don't save the report in ~/.local/state/archcleaner",
    "elegir qué borrar (con resumen y confirmación antes de tocar nada)":
        "choose what to delete (with a summary and confirmation before touching anything)",
    "muestra qué se haría, sin borrar nada": "show what would be done, without deleting anything",
    "desinstalar un programa sin dejar rastro (con ficha, plan y confirmación)":
        "uninstall a program without a trace (with overview, plan and confirmation)",
    "programa": "program",
    "nombre del programa (si no, se elige de una lista)": "program name (otherwise, pick it from a list)",
    "muestra la ficha y el plan, sin tocar nada": "show the overview and the plan, without touching anything",
    "navegar carpetas ordenadas por peso (con la app)": "browse folders sorted by size (in the app)",
    "carpeta": "folder",
    "carpeta donde empezar (si no, se elige el disco)": "folder to start in (otherwise, pick the drive)",
    "qué creció y qué se achicó desde un análisis anterior (solo lectura)":
        "what grew and what shrank since an earlier analysis (read-only)",
    "comparar con el análisis de hace N días (si no, con el anterior)":
        "compare with the analysis from N days ago (otherwise, with the previous one)",
    "No corras ArchCleaner como root: corre como tu usuario y pide sudo solo cuando lo necesita.":
        "Don't run ArchCleaner as root: it runs as your user and asks for sudo only when needed.",
    "Arrancando…": "Starting…",
    "Informe guardado en {ruta}": "Report saved to {ruta}",

    # ── desinstalar: ficha, plan y verificación ──
    "Restos seguros": "Safe leftovers",
    "Restos probables": "Probable leftovers",
    "Info": "Info",
    "{nombre} sigue instalado": "{nombre} is still installed",
    "  (dependencia que queda sin uso)": "  (dependency left unused)",
    "… y {n} más": "… and {n} more",
    "📦 Se va con pacman:": "📦 Removed with pacman:",
    "⚙️  Servicios que se apagan antes:": "⚙️  Services stopped first:",
    " · activo ahora": " · running now",
    " (de usuario)": " (user)",
    "🧩 Restos que encontré:": "🧩 Leftovers found:",
    "🧩 No encontré restos fuera del paquete.": "🧩 No leftovers found outside the package.",
    "⛔ No se puede desinstalar: {motivo}": "⛔ It can't be uninstalled: {motivo}",
    "Liberarías hasta ": "You'd free up to ",
    "[bold]📋 Ficha[/]": "[bold]📋 Overview[/]",
    "apagar {unidad}": "stop {unidad}",
    "pacman -Rns {paquete}  [SUDO]  (quita {n} paquetes; pacman te pide confirmación)":
        "pacman -Rns {paquete}  [SUDO]  (removes {n} packages; pacman asks for confirmation)",
    "flatpak uninstall --delete-data {app}  + runtimes sin uso": "flatpak uninstall --delete-data {app}  + unused runtimes",
    "Steam desinstala el juego (se abre su ventana)": "Steam uninstalls the game (its window opens)",
    "🔎 verificar que no quede rastro": "🔎 check that no trace is left",
    "📝 Plan: desinstalar {nombre}": "📝 Plan: uninstall {nombre}",
    "✔ Rastro: 0": "✔ Trace left: 0",
    "✘ quedó: {que}": "✘ left behind: {que}",
    "• apareció después: {nombre} ({peso})": "• appeared afterwards: {nombre} ({peso})",
    "• {n} cosas que elegiste conservar siguen ahí ({peso}).": "• {n} things you chose to keep are still there ({peso}).",
    "Espacio liberado: ": "Space freed: ",
    "🔎 Verificación: {nombre}": "🔎 Verification: {nombre}",
    "Otros paquetes lo necesitan: {paquetes}": "Other packages need it: {paquetes}",
    "pacman no lo puede quitar: {error}": "pacman can't remove it: {error}",
    "Se llevaría paquetes vitales del sistema: {paquetes}": "It would take vital system packages with it: {paquetes}",
    "Arrastra {n} paquetes: revisá bien la lista antes de confirmar.":
        "It takes {n} packages with it: check the list carefully before confirming.",
    "AppImage": "AppImage",
    "El AppImage": "The AppImage",
    "El archivo del programa.": "The program file.",
    "shader cache": "shader cache",
    "contenido de Workshop": "Workshop content",
    "prefijo de Proton ({ruta}){marca}": "Proton prefix ({ruta}){marca}",
    "Restos de Steam": "Steam leftovers",
    "Shaders y Workshop del juego: se borran al desinstalar.": "The game's shaders and Workshop content: deleted on uninstall.",
    "Prefijo de Proton": "Proton prefix",
    "El 'Windows falso' del juego. Ahí suelen estar las PARTIDAS GUARDADAS (si el juego no usa la nube de Steam). Tildalo solo si no vas a volver a jugarlo.":
        "The game's 'fake Windows'. SAVED GAMES usually live there (if the game doesn't use Steam Cloud). "
        "Select it only if you won't play it again.",
    "Restos en tu home (seguros)": "Leftovers in your home (safe)",
    "Configuraciones, datos y caché con el nombre exacto del programa.":
        "Configs, data and cache with the program's exact name.",
    "Restos en tu home (probables)": "Leftovers in your home (probable)",
    "Se parecen al nombre del programa, pero no es seguro que sean suyos. Revisalos.":
        "They look like the program's name, but they may not be its own. Check them.",
    "Restos en el sistema": "Leftovers in the system",
    "Archivos que el programa creó por su cuenta (configs, servicios, datos) y que pacman no conoce, así que no los borraría nunca.":
        "Files the program created on its own (configs, services, data) that pacman doesn't know about, so "
        "it would never delete them.",
    "{paquete} ({n} versiones en la caché de pacman)": "{paquete} ({n} versions in the pacman cache)",
    "Caché de pacman": "Pacman cache",
    "Los instaladores descargados de estos paquetes. Sin el programa, no sirven.":
        "The downloaded installers of these packages. Useless without the program.",
    "Caché de yay": "yay cache",
    "Lo que yay descargó y compiló para este paquete.": "What yay downloaded and built for this package.",
    "se borra": "deleted",
    "se borra con sudo rm": "deleted with sudo rm",
    "Desinstalar": "Uninstall",

    # ── historial ──
    "%d/%m %H:%M": "%m/%d %H:%M",
    "hace menos de una hora": "less than an hour ago",
    "hace 1 día": "1 day ago",
    "de espacio libre": "of free space",
    "Lo que más creció:": "What grew the most:",
    "Ninguna carpeta creció más de {minimo}.": "No folder grew more than {minimo}.",
    "📈 Desde el análisis del {fecha}": "📈 Since the analysis of {fecha}",
    "Comparando el análisis del ": "Comparing the analysis of ",
    " con el del ": " with the one of ",
    "  ({hace} antes)": "  ({hace})",
    "Antes": "Before",
    "Ahora": "Now",
    "Cambio": "Change",
    "💽 Libre en {punto}": "💽 Free on {punto}",
    "🟢 Basura sin riesgo": "🟢 Safe junk",
    "🟡 Para revisar": "🟡 To review",
    "Resumen": "Summary",
    "📈 Lo que creció": "📈 What grew",
    "Nada creció más de {minimo}.": "Nothing grew more than {minimo}.",
    "📉 Lo que se achicó": "📉 What shrank",
    "Nada se achicó más de {minimo}.": "Nothing shrank more than {minimo}.",
    "   (cambio neto: {cambio})": "   (net change: {cambio})",
    "Solo se muestran cambios de más de {minimo}. «nueva» = no estaba en el análisis anterior; «ya no está» = se borró.":
        "Only changes over {minimo} are shown. «new» = wasn't in the earlier analysis; «gone» = it was deleted.",
    "  nueva": "  new",
    "  ya no está": "  gone",
    "tocá 🔄 Actualizar": "press 🔄 Refresh",
    "corré «archcleaner analizar»": "run «archcleaner analyze»",
    "Todavía no hay historial: se empieza a guardar con cada análisis completo. Analizá hoy ({como}) y volvé otro día para ver qué creció.":
        "There's no history yet: it's saved with every full analysis. Analyze today ({como}) and come back "
        "another day to see what grew.",
    "Hay un solo análisis guardado: hace falta otro para comparar. Volvé a analizar más adelante (o {como} para analizar ahora).":
        "There's only one saved analysis: another one is needed to compare. Analyze again later (or {como} "
        "to analyze now).",

    # ── informe ──
    "borrar": "delete",
    "vaciar": "empty",
    "papelera": "trash",
    "comando": "command",
    "  Para limpiar: ": "  To clean: ",
    "archcleaner limpiar": "archcleaner clean",
    "   ·   los 🟢 vienen tildados, los 🟡 los elegís vos": "   ·   🟢 come pre-selected, you pick the 🟡 ones",
    "   análisis de disco": "   disk analysis",
    "%d/%m/%Y %H:%M": "%Y-%m-%d %H:%M",
    "Modo solo lectura: no se borró nada.": "Read-only mode: nothing was deleted.",
    "Disco": "Drive",
    "Uso": "Usage",
    "Libre": "Free",
    "[bold]💽 Discos[/]": "[bold]💽 Drives[/]",
    "🟢 Sin riesgo": "🟢 Risk-free",
    "🟡 Si revisás": "🟡 If you review",
    "(gigantes y Workshop aparte)": "(huge files and Workshop not included)",
    "[bold]✨ Podés liberar[/]": "[bold]✨ You can free[/]",
    "Peso": "Size",
    "Qué es": "What it is",
    "Categoría": "Category",
    "Cómo": "How",
    "[bold]📋 Qué encontré[/]": "[bold]📋 What I found[/]",
    "Cómo se limpia: ": "How it's cleaned: ",
    "  (con {programas} cerrado)": "  (with {programas} closed)",
    "+ hay carpetas sin permiso de lectura: puede pesar más.": "+ some folders couldn't be read: it may be bigger.",
    " 📂  DÓNDE ESTÁ EL PESO ": " 📂  WHERE THE SPACE GOES ",
    "  Carpetas de más de 1 GB, de mayor a menor. Las barras son relativas al total del disco.":
        "  Folders over 1 GB, largest first. Bars are relative to the drive's total.",
    "~ (tu home)": "~ (your home)",
    "/ (sistema, sin tu home)": "/ (system, without your home)",
    "{n} carpetas sin permiso de lectura no se pudieron medir.": "{n} folders without read permission couldn't be measured.",
    "⚠ Avisos": "⚠ Warnings",

    # ── limpiar: plan y resultado ──
    "⚠ Se borra PARA SIEMPRE ({peso})": "⚠ Deleted FOREVER ({peso})",
    "Qué": "What",
    "  ({n} de {total})": "  ({n} of {total})",
    "⚠ {programas} está abierto: cerralo o «{titulo}» se va a saltear.":
        "⚠ {programas} is open: close it or «{titulo}» will be skipped.",
    "Se libera ahora: ": "Freed now: ",
    "Va a la papelera: ": "Goes to the trash: ",
    " (se libera cuando la vacíes)": " (freed when you empty it)",
    "[bold]📝 Plan de limpieza[/]": "[bold]📝 Cleanup plan[/]",
    "Liberado": "Freed",
    "Libre ahora": "Free now",
    "{ok} de {total} tareas completas": "{ok} of {total} tasks completed",
    "   ·   registro en ": "   ·   log at ",
    "Lo que fue a la papelera se puede recuperar desde la papelera de tu gestor de archivos.":
        "What went to the trash can be restored from your file manager's trash.",
    "[bold]✅ Listo[/]": "[bold]✅ Done[/]",

    # ── programas ──
    "Tamaño": "Size",
    "Menos usados": "Least used",
    "Nombre": "Name",
    "Recién instalados": "Recently installed",
    "juego · appid {appid} · {donde}": "game · appid {appid} · {donde}",
    "hoy": "today",
    "hace {n} d": "{n}d ago",
    "hace {n} meses": "{n} months ago",
    "hace {n} años": "{n} years ago",

    # ── app: flujos ──
    "Atrás": "Back",
    "Adelante": "Forward",
    "🔍 Analizando el disco…": "🔍 Analyzing the disk…",
    "Datos actualizados.": "Data refreshed.",
    "🔍 Análisis de disco": "🔍 Disk analysis",
    "🧹 Limpiar ahora": "🧹 Clean now",
    "Solo lectura: no se borró nada. Rueda del mouse o flechas para recorrer.":
        "Read-only: nothing was deleted. Mouse wheel or arrow keys to scroll.",
    "No existe la carpeta {ruta}": "The folder {ruta} doesn't exist",
    "📈 Qué creció": "📈 What grew",
    "🔍 Analizar ahora": "🔍 Analyze now",
    "No quedó nada elegido.": "Nothing is selected.",
    "📝 Plan de limpieza": "📝 Cleanup plan",
    "🧹 Limpiando": "🧹 Cleaning",
    "📦 Buscando programas instalados…": "📦 Looking for installed programs…",
    "🔎 Investigando {nombre}…": "🔎 Investigating {nombre}…",
    "{nombre} ya no está instalado.": "{nombre} is no longer installed.",
    "Ficha: todo lo que se va y todo lo que dejaría. No se tocó nada.":
        "Overview: everything that goes and everything it would leave behind. Nothing was touched.",
    "📦 {nombre}: ¿qué restos borro?": "📦 {nombre}: which leftovers should I delete?",
    "\nLa desinstalación no se completó: no toqué los restos.":
        "\nThe uninstall didn't complete: I didn't touch the leftovers.",
    "Aparecieron restos nuevos": "New leftovers appeared",
    "Después de desinstalar quedaron cosas que antes eran del paquete (pacman deja las carpetas con archivos que no son suyos):\n\n":
        "After uninstalling, some things that used to belong to the package remained (pacman leaves folders "
        "containing files that aren't its own):\n\n",
    "🗑 Borrarlos también": "🗑 Delete them too",
    "Dejarlos": "Keep them",
    "📦 Desinstalando {nombre}": "📦 Uninstalling {nombre}",
    "… y {n} errores más (ver el log)": "… and {n} more errors (see the log)",
    "  puede tardar unos minutos…": "  this can take a few minutes…",
    "antes de desinstalar {nombre}": "before uninstalling {nombre}",
    "snapshot creada": "snapshot created",
    "No se pudo crear la snapshot": "The snapshot couldn't be created",
    "¿Seguir igual sin snapshot?": "Continue anyway without a snapshot?",
    "Seguir sin snapshot": "Continue without a snapshot",
    "sigo sin snapshot": "continuing without a snapshot",
    "🕒 Snapshot de Timeshift": "🕒 Timeshift snapshot",
    "Apagar {unidad}": "Stop {unidad}",
    "⚙️  Apagar el servicio {unidad}": "⚙️  Stop the {unidad} service",
    "  esperando a que Steam borre {archivo}…": "  waiting for Steam to delete {archivo}…",
    "⏳ Esperando a Steam: {nombre}": "⏳ Waiting for Steam: {nombre}",
    "Se abrió Steam con su ventana de desinstalación. ": "Steam opened its uninstall window. ",
    "Confirmá ahí.": "Confirm there.",
    "ArchCleaner se da cuenta solo cuando Steam termina y sigue con la limpieza.":
        "ArchCleaner notices by itself when Steam is done and continues with the cleanup.",
    "cancelado (el juego sigue instalado)": "cancelled (the game is still installed)",
    "Steam lo desinstaló (detectado automáticamente)": "Steam uninstalled it (detected automatically)",
    "🎮 Desinstalar {nombre} (Steam)": "🎮 Uninstall {nombre} (Steam)",
    "Desinstalar {nombre}": "Uninstall {nombre}",
    "sigue instalado": "still installed",
    " (¿cancelaste en pacman?)": " (did you cancel in pacman?)",
    "📦 Desinstalar {nombre}": "📦 Uninstall {nombre}",

    # ── pantallas comunes ──
    "Volver": "Back",
    "Actualizar": "Refresh",
    "🔄 Actualizar": "🔄 Refresh",
    "Cerrar": "Close",
    "🔥 Borrado definitivo": "🔥 Permanent deletion",
    "Esto ": "This ",
    "no se puede deshacer": "can't be undone",
    ". Para confirmar, escribí ": ". To confirm, type ",
    "🔥 Borrar para siempre": "🔥 Delete forever",
    "🗑 Mejor a la papelera": "🗑 Trash it instead",
    "¿Qué se borra definitivamente?": "What gets deleted permanently?",
    "Lo que no tildes va a la papelera.": "Whatever you don't select goes to the trash.",
    "Seguir ▸": "Continue ▸",

    # ── ejecución ──
    "  Esta terminal no permite apartar la app para responder: corré el comando a mano:\n  ":
        "  This terminal can't set the app aside to answer: run the command by hand:\n  ",
    "🔐 Necesito permisos de administrador: escribí tu contraseña.": "🔐 I need administrator rights: type your password.",
    "pacman te muestra lo que quita y pide confirmación. Después ArchCleaner vuelve solo.":
        "pacman shows what it removes and asks for confirmation. ArchCleaner comes back by itself afterwards.",
    "  sin permisos de administrador: salteado": "  no administrator rights: skipped",
    "Trabajando… no cierres la terminal.": "Working… don't close the terminal.",
    "Salir": "Quit",
    "error inesperado:\n": "unexpected error:\n",
    "\nEse paso era necesario para seguir: me detengo acá.": "\nThat step was required to continue: stopping here.",
    "error al terminar:\n": "error while finishing:\n",
    "✅ Listo.": "✅ Done.",
    "⚠ Terminó con avisos: revisá el detalle.": "⚠ Finished with warnings: check the details.",

    # ── explorar ──
    "Subir": "Up",
    "Borrar": "Delete",
    "Abrir en el gestor de archivos": "Open in the file manager",
    "Inicio": "Home",
    "No se puede leer {carpeta}: {error}": "Can't read {carpeta}: {error}",
    "📂 Explorar": "📂 Explore",
    "clic/enter entrar · ⌫ subir · Supr papelera · Shift+Supr borrar · o abrir carpeta · F5 medir":
        "click/enter open · ⌫ up · Del trash · Shift+Del delete · o open folder · F5 measure",
    "← Subir": "← Up",
    "📂 Abrir": "📂 Open",
    "🗑 Papelera": "🗑 Trash",
    "🔥 Borrar": "🔥 Delete",
    "(carpeta vacía)": "(empty folder)",
    "nueva": "new",
    "{n} elementos": "{n} items",
    "Fuera de tu home y de los discos de datos: acá solo se mira.":
        "Outside your home and data drives: this is look-only.",
    "Peso: ": "Size: ",
    "sin medir": "not measured",
    "   ·   Modificado: ": "   ·   Modified: ",
    "En el análisis del {fecha} no estaba (o pesaba menos de 1 MB).":
        "It wasn't in the analysis of {fecha} (or it was under 1 MB).",
    "En el análisis del {fecha} pesaba {peso}": "In the analysis of {fecha} it was {peso}",
    ", igual que ahora.": ", same as now.",
    "🔒 No se puede borrar desde acá: {motivo}": "🔒 Can't be deleted from here: {motivo}",
    "Abriendo {carpeta}": "Opening {carpeta}",
    "🔒 No se puede": "🔒 Not allowed",
    "🗑 Mandar a la papelera": "🗑 Move to the trash",
    "\n\nSe puede recuperar desde la papelera de tu gestor de archivos. El espacio se libera al vaciarla.":
        "\n\nIt can be restored from your file manager's trash. The space is freed when you empty it.",
    "🗑 A la papelera": "🗑 To the trash",
    "Borrando {nombre}…": "Deleting {nombre}…",
    "Mandando a la papelera {nombre}…": "Moving {nombre} to the trash…",
    "Listo": "Done",
    "No se pudo": "It couldn't be done",
    "Midiendo de nuevo…": "Measuring again…",
    "Actualizado.": "Refreshed.",
    "Tu home": "Your home",
    "/  (sin tu home)": "/  (without your home)",
    "  disco ": "  drive ",
    " · {libre} libres": " · {libre} free",
    "del último análisis": "from the last analysis",
    "📂 ¿Qué querés explorar?": "📂 What do you want to explore?",
    "Pesos medidos {cuando} · adentro, 🔄 Actualizar vuelve a medir":
        "Sizes measured {cuando} · inside, 🔄 Refresh measures again",
    "…o escribí una carpeta (ej. ~/Descargas) y enter": "…or type a folder (e.g. ~/Downloads) and press enter",

    # ── qué creció ──
    "Análisis anterior": "Previous analysis",
    "Hace 1 semana": "1 week ago",
    "Hace 1 mes": "1 month ago",
    "Comparar con…": "Compare with…",
    "Último análisis: {fecha}. Solo lectura: no se toca nada.": "Last analysis: {fecha}. Read-only: nothing is touched.",
    "Comparar con:": "Compare with:",
    "📅 Otra fecha…": "📅 Another date…",
    "El análisis más viejo que hay es del {fecha}: comparo con ese.":
        "The oldest analysis available is from {fecha}: comparing with that one.",
    "📅 ¿Con qué análisis comparo?": "📅 Which analysis should I compare with?",
    "No hay análisis anteriores guardados.": "There are no earlier saved analyses.",
    "   libre en /: {libre}": "   free on /: {libre}",

    # ── menú ──
    "Analizar": "Analyze",
    "informe completo de qué ocupa espacio · solo lectura": "full report of what takes up space · read-only",
    "Limpiar": "Clean",
    "elegís qué borrar, ves el plan y confirmás": "pick what to delete, see the plan and confirm",
    "Simulacro": "Dry run",
    "lo mismo que Limpiar, pero sin borrar nada": "same as Clean, but deleting nothing",
    "un programa sin dejar rastro · con ficha y plan": "a program, without a trace · with overview and plan",
    "vuelve a analizar el disco y refresca las tarjetas": "analyze the disk again and refresh the cards",
    "Explorar": "Explore",
    "navegar carpetas ordenadas por peso (y borrar)": "browse folders sorted by size (and delete)",
    "Qué creció": "What grew",
    "comparar con análisis anteriores: qué creció y qué se achicó": "compare with earlier analyses: what grew and what shrank",
    "analizador y limpiador de disco para Arch Linux": "disk analyzer and cleaner for Arch Linux",
    "libre en / {grafica}": "free on / {grafica}",
    "Todavía no analizaste.\nElegí 🔍 Analizar.": "No analysis yet.\nChoose 🔍 Analyze.",
    "🟢 sin riesgo": "🟢 risk-free",
    "🟡 si revisás": "🟡 if you review",
    "Todavía no limpiaste nada.": "Nothing cleaned yet.",
    "{ok} de {total} tareas ok": "{ok} of {total} tasks ok",
    "💽 Discos": "💽 Drives",
    "📊 Último análisis": "📊 Last analysis",
    "✨ Última limpieza": "✨ Last cleanup",
    "moverse    ": "move    ",
    "elegir    ": "select    ",
    "atajos    ": "shortcuts    ",
    "salir": "quit",

    # ── plan ──
    "Cancelar": "Cancel",
    "🧹 Ejecutar": "🧹 Run",
    "SIMULACRO: podés mirar todo, pero no se va a ejecutar nada.": "DRY RUN: you can look at everything, but nothing will run.",
    "Todavía no se tocó nada. Revisá y confirmá abajo.": "Nothing has been touched yet. Review and confirm below.",
    "\n🗑  Lo que va a la papelera suma ": "\n🗑  What goes to the trash adds up to ",
    ". ¿Qué hacemos con eso?": ". What should we do with it?",
    "Papelera: se puede recuperar (el espacio se libera al vaciarla)":
        "Trash: it can be restored (the space is freed when you empty it)",
    "Definitivo: libera el espacio ya, no se puede deshacer": "Permanent: frees the space now, can't be undone",
    "Elegir grupo por grupo": "Choose group by group",
    "\n🕒 Timeshift": "\n🕒 Timeshift",
    "Crear una snapshot antes (para poder volver atrás si algo sale mal)":
        "Create a snapshot first (so you can roll back if something goes wrong)",
    "🏠 Inicio": "🏠 Home",
    "No se confirmó el borrado definitivo: eso va a la papelera.":
        "Permanent deletion wasn't confirmed: that goes to the trash.",

    # ── lista de programas ──
    "Ordenar": "Sort",
    "📦 Desinstalar": "📦 Uninstall",
    "{n} programas instalados": "{n} installed programs",
    "\nElegir no desinstala nada: primero vas a ver la ficha completa.":
        "\nSelecting doesn't uninstall anything: you'll see the full overview first.",
    "🔎 Escribí para buscar (nombre, descripción, origen)…": "🔎 Type to search (name, description, source)…",
    "Ver ficha ▸": "Overview ▸",
    "Ordenar por:": "Sort by:",
    "«sin uso» = no se abrió desde que se instaló o actualizó": "«unused» = not opened since it was installed or updated",
    "nunca jugado": "never played",
    "sin uso": "unused",

    # ── selección ──
    "Tildar": "Select",
    "Solo 🟢": "Only 🟢",
    "Ninguno": "None",
    "Continuar": "Continue",
    "🧹 Elegí qué limpiar": "🧹 Choose what to clean",
    "Continuar ▸": "Continue ▸",
    "seleccionado: ": "selected: ",
    "\nNada se borra todavía: después vas a ver el plan y confirmar.   ":
        "\nNothing is deleted yet: next you'll see the plan and confirm.   ",
    "clic o espacio: ": "click or space: ",
    "tildar/destildar": "select/unselect",
    "   (con {programas} cerrado)": "   (with {programas} closed)",

    " de {total}": " of {total}",

    "libres": "free",
    "liberados": "freed",
    "{n} grupos": "{n} groups",
}
