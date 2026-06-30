# Οδηγίες & Κανόνες Ανάπτυξης AI (AI Reminders)

*Αυτό το αρχείο διαβάζεται και λαμβάνεται υπόψη από τον AI agent κατά την εκκίνηση του τρέχοντος project για την αποφυγή επαναλαμβανόμενων διευκρινίσεων.*

## Βασικοί Κανόνες (Σημαντικοί)

1. **Package / Dependency Management:** 
   - Χρησιμοποιούμε **ΠΑΝΤΟΤΕ** `uv`. 
   - Δεν τρέχουμε «γυμνές» pip εντολές. Όταν θέλουμε να προσθέσουμε κάτι ή να τρέξουμε κάτι, αξιοποιούμε εντολές όπως `uv pip install ...` ή `uv add ...` ή `uv run ...` αναλόγως του αν διαχειριζόμαστε project file (`pyproject.toml`) ή τοπικό venv.
2. **Framework:** 
   - Το project χρησιμοποιεί τη βιβλιοθήκη **Flet** (Material design UI). Πρέπει να παραμένουμε σε προδιαγραφές που λειτουργούν ομαλά με τις νεότερες εκδόσεις του Flet.
3. **Βάση Δεδομένων & Cloud:** 
   - Η βάση μας είναι η **MongoDB Atlas** (Cloud). Ακόμα κι αν μείνουν παλιά αρχεία όπως `notespy.db` / `migrate...` στο σύστημα, η τρέχουσα υλοποίηση (Production-ready) διαβάζει και γράφει μόνο στην Atlas μέσω του `database.py`.
4. **Pyinstaller & Build:** 
   - Δημιουργούμε εκτελέσιμα (.exe) χρησιμοποιώντας **αποκλειστικά** την εντολή: `uv run pyinstaller <όνομα_αρχείου.spec>`.
   - **Η τρέχουσα (τελευταία) έκδοση** του spec αρχείου είναι: `NoteSpy-Latest.spec`. Πάντα χρησιμοποιούμε αυτή εκτός αν ζητηθεί παρέμβαση προσωποποιημένη.
   - **Android / Linux Build:** Για παραγωγή APK τρέχουμε **αποκλειστικά** το script `./build_apk.sh`. Το script ρυθμίζει JAVA_HOME, GRADLE_OPTS και τρέχει `uv run flet build apk` με τις κατάλληλες παραμέτρους. Ποτέ δεν τρέχουμε `flet build apk` χειροκίνητα.
5. **Εκδόσεις (Versioning):** 
   - Οι εκδόσεις του προγράμματος (version) αυξάνονται πάντοτε κατά **0.0.1** και φροντίζουμε να παράγουμε/αποθηκεύουμε releases κάθε φορά.
   - **Τρέχουσα έκδοση:** `1.0.0` (build number `1`).
   - Τα versions πρέπει να ενημερώνονται ταυτόχρονα σε: `pyproject.toml` (2 σημεία: `[project].version` και `[tool.flet].version`/`build_number`), `build_apk.sh`, `main.py` (title).
6. **UI Icons (Flet):** 
   - Αντί για `flet.controls.material.icons` πρέπει **ΠΑΝΤΟΤΕ** να χρησιμοποιούμε τα **`ft.CupertinoIcons`**, τα οποία είναι διαθέσιμα με ασφάλεια σε κάθε build εκδοχής.
7. **Git / GitHub:** 
   - Εάν ζητηθεί να γίνει ενημέρωση στο GitHub repository, χρησιμοποιούμε το Command Line Tool **`gh`** που είναι ήδη εγκατεστημένο και συνδεδεμένο στο σύστημα.
8. **Γλώσσα Τεκμηρίωσης:** 
   - Κάθε έγγραφο τεκμηρίωσης, αλλαγών (changelog) και το `README.md` παραδίδεται αυστηρά και **ΠΑΝΤΟΤΕ στα Ελληνικά**.

## Αρχιτεκτονική Ήχου (Audio Architecture) — ΣΗΜΑΝΤΙΚΟ

Στο Flet 0.83+, οι Audio controls **δεν ανήκουν** στο κεντρικό `flet` package. Υπάρχουν ως ξεχωριστά πακέτα:

| Πακέτο | Import | Χρήση | Plugin Registration |
|--------|--------|-------|---------------------|
| `flet-audio` | `from flet_audio import Audio` | Αναπαραγωγή ήχου (TTS playback) | `"flet_audio" = "Audio"` |
| `flet-audio-recorder` | `from flet_audio_recorder import AudioRecorder` | Εγγραφή φωνής (STT) | `"flet_audio_recorder" = "AudioRecorder"` |

### Κρίσιμα σημεία:
- Τα plugins πρέπει να δηλώνονται στο `pyproject.toml` κάτω από `[tool.flet.plugins]`
- Η `Audio.src` δέχεται: **URL**, **asset path**, **base64 string**, ή **raw bytes**
- Για Android TTS, στέλνουμε τα gTTS MP3 **ως base64 string** (αποφεύγουμε `file://` URIs που δεν δουλεύουν σε mobile)
- Τα Audio controls προστίθενται στο `page.services` (ΟΧΙ `page.overlay`)
- Οι μέθοδοι `.play()`, `.pause()` κλπ. είναι **async** — χρήση `page.run_task()` αν καλούνται από sync context
- Στο desktop (Linux/Windows) χρησιμοποιούμε `pygame.mixer` σε background thread (πιο αξιόπιστο)
- **ΠΡΟΣΟΧΗ:** Το `pygame` δεν έχει ARM wheels → **ΠΟΤΕ στα main `dependencies`**, μόνο στα `[project.optional-dependencies].desktop`. Αλλιώς σπάει το APK build.
- Για desktop dev/run, εγκαθιστούμε χειροκίνητα: `uv pip install pygame>=2.6.1` (το `uv sync --extra desktop` μπορεί να αποτύχει αν λείπει η `portaudio.h` για pyaudio)
- **Linux εκτελέσιμα:** Χτίζονται με `uv run pyinstaller NoteSpy_v98_linux.spec`, **ΟΧΙ** με `flet build`. Η `flet build apk` είναι αποκλειστικά για Android.
- **ΚΡΙΣΙΜΟ:** Ο `pyinstaller` πρέπει να είναι εγκατεστημένος **μέσα στο venv** (`uv pip install pyinstaller`). Αν τρέξει ο system pyinstaller (π.χ. `/home/user/.local/bin/pyinstaller`), δεν βλέπει τα packages του project → `ModuleNotFoundError`.
- Το Flet χρησιμοποιεί lazy imports (`__getattr__`) — ο PyInstaller δεν τα εντοπίζει αυτόματα. Η λύση είναι `collect_all('flet')` μέσα στο spec αρχείο.

### Χρωματική Παλέτα (Theme)
- **Dark mode** με **GREEN color scheme** (GREEN_900 → GREEN_400)
- Background: `#0A140E`, Surface: `#1A261F`, Accent: `#4CAF50` (Material Green 500)
- Ορίζεται στο `main.py` μέσω `ft.Theme(color_scheme=ft.ColorScheme(...))`
- Glass-card effect: `ft.Colors.with_opacity(0.05, ft.Colors.WHITE)` + blur

## Πιθανά Προβλήματα & Σημεία Προσοχής (Gotchas)

1. **Διαχείριση Περιβάλλοντος (ENV Secrets):** 
   - Για να λειτουργεί η εφαρμογή όταν γίνεται μεταγλώττιση σε `exe`, η φόρτωση του `.env` στο `database.py` γίνεται χρησιμοποιώντας το `sys._MEIPASS` (το οποίο αφορά το PyInstaller).
   - *Προσοχή:* Αν γίνει αλλαγή της δομής φακέλων, πρέπει να ανανεωθούν και τα datas στο `NoteSpy_Latest.spec`.
2. **Ελληνικά & PDF Files (`reportlab`):** 
   - Το αρχείο `pdf_manager.py` φορτώνει TrueType Fonts (arial.ttf, segoeui.ttf κλπ.) από τα default συστημικά PC/Mac μονοπάτια. Αν χρειαστεί να τρέξει η εφαρμογή σε μηχάνημα που δεν έχει αυτές τις γραμματοσειρές, τα ελληνικά μπορεί να βγουν "κουτάκια" στο PDF.
3. **Google Gemini (AI Κατηγοριοποίηση):** 
   - Όταν γίνεται παρατεταμένη χρήση (AI Categorize All), ίσως "κόβει" λόγω Rate Limits (ειδικά αν χρησιμοποιούνται δωρεάν keys χωρίς delay ανά note).
4. **Αναγνώριση Φωνής (Voice & Mic Access):** 
   - Σε Windows το `SpeechRecognition` ή `pyaudio` μπορεί να παραπονεθεί αν δεν υπάρχει εξορισμού μικρόφωνο ή αν είναι απενεργοποιημένο. Το `audio_manager.py` κάνει robust error handling.
   - Σε Android η εγγραφή γίνεται μέσω `flet-audio-recorder` (AudioRecorder) και η αναγνώριση μέσω `recognize_speech_from_file()`.
5. **Δικτυακή Ενεργότητα:** 
   - Αφού βασιζόμαστε 100% στο cloud (MongoDB Atlas) και στο Gemini API, χωρίς Internet Connection το Application (ή κομμάτια αυτού) θα αποτύχουν. Είναι σκόπιμο να χειριζόμαστε τα exceptions αν το "ping" πέσει.
6. **Build Memory:** 
   - Το APK build καταναλώνει πολλή μνήμη. Το `build_apk.sh` ρυθμίζει `GRADLE_OPTS="-Xmx2g -Dorg.gradle.daemon=false"` για σταθερότητα.
   
## Flet & Android Lessons Learned (Μαθήματα που πήραμε)

1. **Flet CupertinoIcons:**
   - Μην υποθέτετε/συνδυάζετε ονόματα εικονιδίων με καταλήξεις (π.χ. `_SOLID` ή `_OPEN_SOLID`). Χρησιμοποιείτε αποκλειστικά έγκυρα εικονίδια από το namespace `ft.CupertinoIcons` (π.χ. `FOLDER_OPEN` αντί `FOLDER_OPEN_SOLID`, `DOC_TEXT` αντί `DOC_SOLID`).
2. **Κύκλος Ζωής Στοιχείων Flet (Mounting Lifecycle):**
   - **Κανόνας:** Δεν τροποποιούμε ποτέ τα περιεχόμενα (`.controls`, `.content`) ενός στοιχείου ελέγχου (Control) και δεν καλούμε `page.update()` ή `control.update()` αν αυτό δεν έχει προσαρτηθεί ακόμα ενεργά στην οθόνη (δηλαδή αν `control.page is None`).
   - **Λύση:** Προσθέτουμε πάντα προστατευτικό έλεγχο `if not control.page: return` για να αποφύγουμε το σφάλμα `Control must be added to the page first` κατά την εκκίνηση ή την αλλαγή καρτέλας. Επίσης, στη διαχείριση πλοήγησης, πρώτα προσαρτούμε το view στη σελίδα και μετά το γεμίζουμε με δεδομένα.
3. **Android Mime-Types & Gemini API:**
   - Η βιβλιοθήκη `mimetypes` της Python στο Android επιστρέφει `None` για αρχεία `.m4a` λόγω έλλειψης τοπικής βάσης δεδομένων mimetypes (λείπει το `/etc/mime.types`). 
   - **Λύση:** Κατά το ανέβασμα αρχείων ηχογράφησης στο Gemini SDK, ορίζουμε πάντα ρητά το mimetype: `client.files.upload(file=file_path, config=dict(mime_type="audio/mp4"))`.
4. **Android Audio Recorder Paths:**
   - Στο Android, όταν ο `AudioRecorder` αποθηκεύει με σχετική διαδρομή `../../../notespy_recording.m4a`, το αρχείο αποθηκεύεται στον γονικό φάκελο `files/` της εφαρμογής και όχι στο `files/flet/`. 
   - **Λύση:** Η Python πρέπει να αναζητά το αρχείο στο `os.path.dirname(os.path.dirname(os.getcwd()))`.

5. **Μη-οπτικά Controls (FilePicker, Audio κ.α.):**
   - **Κανόνας:** Μην τα προσθέτετε ποτέ στο `page.overlay`! Αυτό προκαλεί σφάλμα `"Unknown control: FilePicker"` στον client.
   - **Λύση:** Πρέπει να τα προσθέτετε αποκλειστικά στη συλλογή υπηρεσιών `page.services.append(control)`.
6. **Κλήσεις μεθόδων FilePicker:**
   - **Κρίσιμο:** Οι μέθοδοι του `FilePicker` (π.χ. `get_directory_path()`, `pick_files()`) είναι **async** (coroutines) σε αυτή την έκδοση και επιστρέφουν το αποτέλεσμα **απευθείας ως επιστρεφόμενη τιμή της `await` έκφρασης** (και **ΔΕΝ** πυροδοτούν callback `on_result`). Συνεπώς, δεν χρησιμοποιούμε `on_result` callback, αλλά παίρνουμε την τιμή απευθείας: `path = await self.file_picker.get_directory_path(...)`. Αν κληθούν σύγχρονα, επιστρέφουν `RuntimeWarning: coroutine was never awaited`.
7. **Ιδιότητες ft.Image (src) και updates:**
   - **Κανόνας:** Το `ft.Image` απαιτεί υποχρεωτικά την παράμετρο `src` στον constructor. Αν δοθεί `src=""`, ο Flutter client εμφανίζει σφάλμα `"A valid src value must be specified"` στο UI.
   - **Κρίσιμο:** Η κλάση `ft.Image` **δεν** διαθέτει ιδιότητα `src_base64` σε αυτήν την έκδοση. Η ιδιότητα `src` δέχεται απευθείας: URL/μονοπάτι αρχείου, base64 string ή raw `bytes`.
   - **Λύση:** Αρχικοποιούμε το `src` με ένα διαφανές pixel 1x1 σε μορφή base64 (`"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="`), και στη συνέχεια ενημερώνουμε δυναμικά την εικόνα αναθέτοντας τα raw `bytes` απευθείας στην ιδιότητα `src` (`self.preview_image.src = image_bytes`).
8. **Δυναμικό Redraw & Repaint Freeze (Windows Desktop):**
   - **Κανόνας:** Σε ορισμένα Windows περιβάλλοντα, ο Flutter desktop client ενδέχεται να μην κάνει redraw την οθόνη όταν δέχεται updates από background threads (π.χ. μετά από επεξεργασία εικόνας), και να απαιτεί αλλαγή focus (ή resize) του παραθύρου για να εμφανίσει τις αλλαγές.
   - **Λύση:** Μην επαναχρησιμοποιείτε το ίδιο control instance της εικόνας, αλλά δημιουργήστε ένα **νέο** `ft.Image` control και αναθέστε το στο container. Για να εξαναγκάσετε το redraw ακαριαία, αυξομειώστε το πλάτος του παραθύρου κατά 1px προγραμματιστικά στο τέλος του update:
     ```python
     self.page.update()
     if not self.page.web:
         current_width = self.page.window_width
         if current_width:
             self.page.window_width = current_width + 1
             self.page.update()
             self.page.window_width = current_width
             self.page.update()
     ```

---
*Όταν ο χρήστης ζητά αλλαγές σ' αυτό το project, ξεκινάμε με γνώμονα αυτούς τους κανόνες και συνεχίζουμε άμεσα την εκτέλεση χωρίς να απαιτούμε παραπάνω context.*

