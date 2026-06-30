# Κανόνες Ανάπτυξης Έργου (Project Rules)

## Κανόνας Handsoff (^)
- Όταν ο χρήστης στέλνει μόνο το σύμβολο `^` (caret), σημαίνει **handsoff**: ο AI agent πρέπει να συνεχίσει αυτόνομα από εκεί που σταμάτησε, χωρίς να ζητάει διευκρινίσεις ή επιβεβαίωση. Ολοκληρώνει όλα τα εκκρεμή βήματα μέχρι τέλους.

## Κανόνας Εκδόσεων (Versioning)
- Σε κάθε αλλαγή που γίνεται στον κώδικα ή στη λειτουργικότητα, η έκδοση αυξάνεται κατά **0.0.1**.
- Τα versions πρέπει να ενημερώνονται ταυτόχρονα σε: `pyproject.toml` (2 σημεία: `[project].version` και `[tool.flet].version`/`build_number`), και `main.py` (στο header title text).

## Κανόνας Εκτέλεσης & Αποσφαλμάτωσης
- Ο AI agent οφείλει να τρέχει και να αποσφαλματώνει (debug) τον κώδικα πάντοτε ο ίδιος (χρησιμοποιώντας τις κατάλληλες εντολές/εργαλεία εκτέλεσης) μέχρι να βεβαιωθεί ότι δεν υπάρχουν συντακτικά λάθη (syntax errors) ή λάθη εκτέλεσης (runtime errors).
- Μόνο αφού ο κώδικας εκτελείται επιτυχώς χωρίς σφάλματα, παραδίδεται στον χρήστη για τελικό έλεγχο.

## Κανόνες Συμβατότητας Flet (Flet Compatibility Rules)
Κατά την ανάπτυξη εφαρμογών Flet (ειδικά για την έκδοση 0.85.x/0.83+ που είναι εγκατεστημένη στο venv), ακολουθούμε αυστηρά τους παρακάτω κανόνες σχεδίασης και ιδιοτήτων για την αποφυγή AttributeError, TypeError ή Unknown Control σφαλμάτων:

1. **Μη-οπτικά Controls (FilePicker, Audio κ.α.):**
   - **Κανόνας:** Ποτέ μην προσθέτετε non-visual controls (όπως `ft.FilePicker` ή `ft.Audio`) στο `page.overlay`! Αυτό προκαλεί σφάλμα `"Unknown control: FilePicker"` στον client.
   - **Λύση:** Πρέπει να τα προσθέτετε αποκλειστικά στη συλλογή υπηρεσιών `page.services.append(control)`.
   - **Κρίσιμο:** Οι μέθοδοι του `FilePicker` (π.χ. `get_directory_path()`, `pick_files()`) είναι **async** (coroutines) σε αυτή την έκδοση και επιστρέφουν το αποτέλεσμα (διαδρομή ή λίστα αρχείων) **απευθείας ως επιστρεφόμενη τιμή της `await` έκφρασης**, και **ΔΕΝ** πυροδοτούν callback `on_result`. Συνεπώς, δεν χρησιμοποιούμε `on_result` callback, αλλά παίρνουμε την τιμή απευθείας: `path = await self.file_picker.get_directory_path(...)`. Αν κληθούν σύγχρονα (π.χ. μέσω `lambda`), δεν θα κάνουν απολύτως τίποτα και θα επιστρέψουν `RuntimeWarning: coroutine was never awaited`.
   - **Παράδειγμα:**
     ```python
     self.file_picker = ft.FilePicker()
     self.page.services.append(self.file_picker)
     ```

2. **Ανάθεση Event Handlers (Callbacks):**
   - **Κανόνας:** Ορισμένα controls (όπως `ft.Dropdown`) δεν δέχονται callbacks (π.χ. `on_change`) ως keyword arguments στον constructor τους σε αυτή την έκδοση.
   - **Λύση:** Αρχικοποιήστε το control χωρίς το callback και αναθέστε το callback ως ιδιότητα (property) αμέσως μετά την κατασκευή του:
     ```python
     self.dropdown = ft.Dropdown()
     self.dropdown.on_change = self.on_setting_changed
     ```

3. **Ιδιότητες Padding και Margin:**
   - **Κανόνας:** Μην χρησιμοποιείτε τις βοηθητικές μεθόδους `ft.padding.all()`, `ft.padding.symmetric()` ή `ft.margin.only()`. Το module `ft.padding` / `ft.margin` δεν τις περιέχει σε αυτή την έκδοση (AttributeError).
   - **Λύση:** Χρησιμοποιήστε απευθείας τις κλάσεις `ft.Padding` και `ft.Margin` με positional ή keyword arguments:
     - `ft.Padding(left, top, right, bottom)` (ή `ft.Padding(8, 8, 8, 8)` για all)
     - `ft.Margin(left, top, right, bottom)` (ή `ft.Margin(0, 10, 0, 0)` για only top)

4. **Ιδιότητες Border και Alignment:**
   - **Κανόνας:** Οι βοηθητικές μέθοδοι/ιδιότητες (π.χ. `all`, `center`) ανήκουν στις κλάσεις `ft.Border` και `ft.Alignment` (με κεφαλαίο πρώτο γράμμα) και όχι στα αντίστοιχα lowercase modules (AttributeError).
   - **Λύση:** Χρησιμοποιήστε `ft.Border.all()` και `ft.Alignment.CENTER` (ή `ft.Alignment.TOP_LEFT` σε UPPERCASE).

5. **Κατασκευή Καρτελών (Tabs):**
   - **Κανόνας:** Το `ft.Tab` δεν δέχεται `text` και `content` στον constructor του, και το `ft.Tabs` δεν έχει ιδιότητα `tabs` (TypeError).
   - **Λύση:** Χρησιμοποιήστε τις κλάσεις `ft.TabBar` και `ft.TabBarView` μέσα στο όρισμα `content` του `ft.Tabs`:
     ```python
     tabs = ft.Tabs(
         length=2,
         content=ft.Column(
             controls=[
                 ft.TabBar(tabs=[ft.Tab(label="Tab 1"), ft.Tab(label="Tab 2")]),
                 ft.TabBarView(controls=[view1, view2])
             ]
         )
     )
     ```

6. **Ιδιότητες ft.Container (Decoration):**
   - **Κανόνας:** Το `ft.Container` δεν υποστηρίζει το όρισμα `decoration=ft.BoxDecoration(...)`.
   - **Λύση:** Ορίστε τις ιδιότητες `image`, `border`, `border_radius` κλπ. απευθείας ως ορίσματα στον constructor του `ft.Container`.

7. **Ιδιότητες ft.Colors (of):**
   - **Κανόνας:** Η μέθοδος `ft.Colors.of()` δεν υπάρχει σε αυτή την έκδοση (AttributeError).
   - **Λύση:** Χρησιμοποιήστε απευθείας τις συμβολοσειρές των χρωμάτων (π.χ. `"#1E2D24"` ή `"green"`).

8. **Αρχικοποίηση ft.Image (src):**
   - **Κανόνας:** Σε αυτή την έκδοση, το `ft.Image` απαιτεί υποχρεωτικά την παράμετρο `src` στον constructor. Αν δοθεί κενό αλφαριθμητικό (`src=""`), ο Flutter client θα εμφανίσει σφάλμα `"A valid src value must be specified"` στο UI.
   - **Κρίσιμο:** Η κλάση `ft.Image` **δεν** διαθέτει ιδιότητα `src_base64` σε αυτήν την έκδοση. Η ιδιότητα `src` δέχεται απευθείας: URL/μονοπάτι αρχείου, base64 string ή raw `bytes`.
   - **Λύση:** Αρχικοποιήστε το `src` με ένα διαφανές pixel 1x1 σε μορφή base64, και στη συνέχεια ενημερώστε δυναμικά την εικόνα αναθέτοντας τα raw `bytes` της εικόνας απευθείας στην ιδιότητα `src` (π.χ. `self.preview_image.src = image_bytes`).
     - Διαφανές pixel: `"data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="`

9. **Δυναμική Ενημέρωση ft.Image (Caching / Repaint Bug):**
   - **Κανόνας:** Όταν αλλάζετε δυναμικά το περιεχόμενο μιας εικόνας, αν αναθέσετε απλώς νέα bytes/path στο `image.src` του ίδιου control instance, ο Flutter client ενδέχεται να μην κάνει redraw αμέσως (λόγω caching ή έλλειψης repaint event) και να απαιτεί αλλαγή focus (αλλαγή παραθύρου) για να εμφανίσει την αλλαγή.
   - **Λύση:** Μην επαναχρησιμοποιείτε το ίδιο control instance. Κατασκευάστε ένα **νέο** `ft.Image` control με τις νέες τιμές, αναθέστε το στο `content` του Container/Row/Column, και καλέστε **`page.update()`** αντί για update μόνο του container.
   - **Κρίσιμο (Windows Desktop Repaint Freeze):** Σε ορισμένα Windows περιβάλλοντα, ο Flutter desktop client ενδέχεται να μην κάνει redraw την οθόνη όταν δέχεται updates από background threads, και να απαιτεί αλλαγή focus (ή resize) του παραθύρου για να εμφανίσει τις αλλαγές. Για να το λύσετε αυτό προγραμματιστικά, αυξομειώστε το πλάτος του παραθύρου κατά 1px για να εξαναγκάσετε το λειτουργικό σύστημα να στείλει μήνυμα resize στο Flutter, εξαναγκάζοντας το redraw ακαριαία:
     ```python
     def safe_page_update(self):
         if self.page:
             self.page.update()
             if not self.page.web:
                 current_width = self.page.window_width
                 if current_width:
                     self.page.window_width = current_width + 1
                     self.page.update()
                     self.page.window_width = current_width
                     self.page.update()
     ```
