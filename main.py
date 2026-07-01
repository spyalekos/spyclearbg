import os
import glob
import threading
import base64
import subprocess
from io import BytesIO
import flet as ft
from PIL import Image, ImageOps
import rembg

def make_checkerboard_base64():
    """Δημιουργεί ένα διαφανές μοτίβο σκακιέρας σε base64 για την προεπισκόπηση."""
    # Δημιουργία μιας 16x16 εικόνας σκακιέρας με τα χρώματα του θέματος
    img = Image.new("RGBA", (16, 16), (13, 26, 18, 255)) # Πολύ σκούρο πράσινο
    for y in range(16):
        for x in range(16):
            if (x < 8 and y < 8) or (x >= 8 and y >= 8):
                img.putpixel((x, y), (29, 48, 37, 255)) # Ελαφρώς πιο ανοιχτό πράσινο
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    return base64.b64encode(buffered.getvalue()).decode()

def get_image_bytes(filepath, max_size=600):
    """Φορτώνει την εικόνα, διορθώνει τον προσανατολισμό EXIF, τη μικραίνει για προεπισκόπηση και την επιστρέφει σε bytes."""
    if not filepath or not os.path.exists(filepath):
        return None
    try:
        with Image.open(filepath) as img:
            # Διόρθωση περιστροφής από τα EXIF δεδομένα (π.χ. από κινητά τηλέφωνα)
            img = ImageOps.exif_transpose(img)
            img.thumbnail((max_size, max_size))
            buffered = BytesIO()
            img.save(buffered, format="PNG")
            return buffered.getvalue()
    except Exception as e:
        print(f"Error loading image bytes for {filepath}: {e}")
        return None

class SpyClearBGApp:
    def __init__(self, page: ft.Page):
        self.page = page
        self.folder_path = ""
        self.image_files = []      # Λίστα από dict: {"name": str, "path": str, "selected": bool, "status": str, "result_path": str}
        self.selected_index = -1   # Δείκτης της επιλεγμένης εικόνας για προεπισκόπηση
        self.processing = False    # Κατάσταση επεξεργασίας
        self.sessions = {}         # Cache για τα rembg sessions (αποφυγή επαναλαμβανόμενου φόρτωματος)
        
        # Αρχικές ρυθμίσεις
        self.settings = {
            "model_name": "u2net",
            "alpha_matting": False,
            "alpha_matting_foreground_threshold": 240,
            "alpha_matting_background_threshold": 10,
            "alpha_matting_erode_size": 10,
            "only_mask": False,
            "post_process_mask": False,
            "custom_bg": False,
            "bg_color_r": 255,
            "bg_color_g": 255,
            "bg_color_b": 255,
            "bg_color_a": 255,
            "save_suffix": "_nobg",
            "overwrite": True
        }
        
        # Δημιουργία του checkerboard base64
        self.checkerboard_src = f"data:image/png;base64,{make_checkerboard_base64()}"
        
        # Αρχικοποίηση των UI Controls
        self.setup_ui_controls()
        
    def setup_ui_controls(self):
        # FilePicker για επιλογή φακέλου
        self.file_picker = ft.FilePicker()
        # Στο Flet 0.83+ τα μη-οπτικά controls (FilePicker, Audio) προστίθενται στο page.services αντί για το page.overlay
        self.page.services.append(self.file_picker)
        
        # Sidebar Controls
        self.folder_path_text = ft.Text(
            "Δεν έχει επιλεγεί φάκελος",
            size=12,
            color=ft.Colors.GREY_400,
            italic=True,
            max_lines=1,
            overflow=ft.TextOverflow.ELLIPSIS,
            expand=True
        )
        
        self.btn_select_folder = ft.Button(
            "Επιλογή Φακέλου",
            icon=ft.CupertinoIcons.FOLDER,
            on_click=self.select_folder_click,
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.GREEN_700,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )
        
        self.search_field = ft.TextField(
            hint_text="Αναζήτηση αρχείου...",
            text_size=12,
            height=36,
            content_padding=ft.Padding(8, 8, 8, 8),
            bgcolor="#1A261F",
            border_color="#2D3F34",
            expand=True,
            on_change=lambda _: self.build_images_list_ui()
        )
        
        self.select_all_checkbox = ft.Checkbox(
            label="Όλα",
            value=False,
            on_change=lambda e: self.toggle_select_all(e.control.value),
            fill_color={"": ft.Colors.GREEN}
        )
        
        self.btn_process_selected = ft.Button(
            "Αφαίρεση στα Επιλεγμένα",
            icon=ft.CupertinoIcons.PLAY_FILL,
            on_click=lambda _: self.start_bulk_processing(),
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.GREEN_600,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )
        
        self.images_list_container = ft.Column(
            scroll=ft.ScrollMode.ALWAYS,
            expand=True,
            spacing=5
        )
        
        # Main Preview Area Controls
        self.original_preview_title = ft.Text("Αρχική Εικόνα", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        
        # Διαφανές pixel 1x1 base64 για την αποφυγή σφάλματος "A valid src value must be specified"
        self.transparent_pixel = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
        
        self.original_preview_image = ft.Image(src=self.transparent_pixel, fit="contain")
        self.original_preview_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.CupertinoIcons.PHOTO, size=60, color=ft.Colors.GREY_600),
                    ft.Text("Επιλέξτε μια εικόνα από τη λίστα", size=14, color=ft.Colors.GREY_500)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor="#151515",
            border_radius=10,
            border=ft.Border.all(1, "#2D3F34"),
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=10
        )
        
        self.processed_preview_title = ft.Text("Αποτέλεσμα", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400)
        self.processed_preview_image = ft.Image(src=self.transparent_pixel, fit="contain")
        self.processed_preview_container = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Icon(ft.CupertinoIcons.PHOTO, size=60, color=ft.Colors.GREY_600),
                    ft.Text("Το αποτέλεσμα θα εμφανιστεί εδώ", size=14, color=ft.Colors.GREY_500)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            ),
            image=ft.DecorationImage(
                src=self.checkerboard_src,
                repeat=ft.ImageRepeat.REPEAT
            ),
            border_radius=10,
            border=ft.Border.all(1, "#2D3F34"),
            expand=True,
            alignment=ft.Alignment.CENTER,
            padding=10
        )
        
        # Preview Section Buttons
        self.btn_process_current = ft.Button(
            "Έναρξη Αφαίρεσης Φόντου",
            icon=ft.CupertinoIcons.PLAY_FILL,
            disabled=True,
            on_click=lambda _: self.process_image_index(self.selected_index),
            style=ft.ButtonStyle(
                color=ft.Colors.WHITE,
                bgcolor=ft.Colors.GREEN_600,
                shape=ft.RoundedRectangleBorder(radius=8)
            )
        )
        
        self.btn_open_file = ft.IconButton(
            icon=ft.CupertinoIcons.FOLDER_OPEN,
            icon_color=ft.Colors.WHITE,
            tooltip="Άνοιγμα αρχείου στο σύστημα",
            disabled=True,
            on_click=lambda _: self.open_current_file()
        )
        
        self.btn_view_result = ft.IconButton(
            icon=ft.CupertinoIcons.EYE,
            icon_color=ft.Colors.WHITE,
            tooltip="Προβολή επεξεργασμένου αρχείου",
            visible=False,
            on_click=lambda _: self.view_processed_file()
        )
        
        self.btn_delete_result = ft.IconButton(
            icon=ft.CupertinoIcons.TRASH,
            icon_color=ft.Colors.RED_400,
            tooltip="Διαγραφή αποτελέσματος",
            visible=False,
            on_click=lambda _: self.delete_processed_file()
        )
        
        # Settings Panel Controls
        self.setup_settings_controls()
        
        # Bottom Status Bar Controls
        self.status_text = ft.Text("Έτοιμο. Παρακαλώ επιλέξτε έναν φάκελο.", size=12, color=ft.Colors.GREY_300)
        self.progress_bar = ft.ProgressBar(visible=False, color=ft.Colors.GREEN_400, bgcolor="#1A261F")
        
    def setup_settings_controls(self):
        # AI Models dropdown
        self.dropdown_model = ft.Dropdown(
            label="Μοντέλο AI (Model)",
            value="u2net",
            options=[
                ft.dropdown.Option("u2net", "Standard (u2net) - Γενικής χρήσης"),
                ft.dropdown.Option("u2netp", "Γρήγορο / Ελαφρύ (u2netp)"),
                ft.dropdown.Option("u2net_human_seg", "Ανθρώπινη Φιγούρα (u2net_human)"),
                ft.dropdown.Option("u2net_cloth_seg", "Ρούχα / Μόδα (u2net_cloth)"),
                ft.dropdown.Option("siluela", "Προϊόντα & Αντικείμενα (siluela)"),
                ft.dropdown.Option("isnet-general-use", "ISNet Γενικής Χρήσης (isnet)"),
                ft.dropdown.Option("isnet-anime", "Anime / Σχέδια (isnet-anime)"),
            ],
            bgcolor="#1A261F",
            border_color="#2D3F34",
        )
        self.dropdown_model.on_change = self.on_setting_changed
        
        # Alpha Matting switch
        self.switch_alpha_matting = ft.Switch(
            label="Ενεργοποίηση Alpha Matting (για μαλλιά, πούπουλα κλπ.)",
            value=False,
            on_change=self.on_alpha_matting_toggled
        )
        
        # Alpha Matting Sliders (packed in a container)
        self.slider_fg = ft.Slider(min=0, max=255, value=240, label="Κατώφλι Προσκηνίου (FG): {value}", active_color=ft.Colors.GREEN_400, on_change=self.on_setting_changed)
        self.slider_bg = ft.Slider(min=0, max=255, value=10, label="Κατώφλι Παρασκηνίου (BG): {value}", active_color=ft.Colors.GREEN_400, on_change=self.on_setting_changed)
        self.slider_erode = ft.Slider(min=1, max=50, value=10, label="Μέγεθος Διάβρωσης (Erode): {value}", active_color=ft.Colors.GREEN_400, on_change=self.on_setting_changed)
        
        self.alpha_sliders_container = ft.Column(
            controls=[
                ft.Text("Ρυθμίσεις Alpha Matting:", size=12, weight=ft.FontWeight.BOLD),
                self.slider_fg,
                self.slider_bg,
                self.slider_erode,
            ],
            visible=False,
            spacing=5
        )
        
        # Mask options switches
        self.switch_only_mask = ft.Switch(
            label="Μόνο Μάσκα (Only Mask) - παράγει ασπρόμαυρη μάσκα",
            value=False,
            on_change=self.on_setting_changed
        )
        self.switch_post_process = ft.Switch(
            label="Μετα-επεξεργασία Μάσκας (Post-process Mask)",
            value=False,
            on_change=self.on_setting_changed
        )
        
        # Custom background color switch
        self.switch_custom_bg = ft.Switch(
            label="Προσαρμοσμένο Χρώμα Φόντου (Custom BG)",
            value=False,
            on_change=self.on_custom_bg_toggled
        )
        
        # Custom BG Color Sliders
        self.slider_r = ft.Slider(min=0, max=255, value=255, label="Κόκκινο (R): {value}", active_color=ft.Colors.RED, on_change=self.on_color_changed)
        self.slider_g = ft.Slider(min=0, max=255, value=255, label="Πράσινο (G): {value}", active_color=ft.Colors.GREEN, on_change=self.on_color_changed)
        self.slider_b = ft.Slider(min=0, max=255, value=255, label="Μπλε (B): {value}", active_color=ft.Colors.BLUE, on_change=self.on_color_changed)
        self.slider_a = ft.Slider(min=0, max=255, value=255, label="Διαφάνεια (A): {value}", active_color=ft.Colors.GREY_400, on_change=self.on_color_changed)
        
        self.color_preview_box = ft.Container(
            width=50,
            height=50,
            border_radius=5,
            border=ft.Border.all(1, ft.Colors.WHITE),
            bgcolor="#FFFFFFFF" # Solid White initially
        )
        
        self.color_picker_container = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Text("Προεπισκόπηση Χρώματος:", size=12),
                        self.color_preview_box
                    ],
                    alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                ),
                self.slider_r,
                self.slider_g,
                self.slider_b,
                self.slider_a,
            ],
            visible=False,
            spacing=5
        )
        
        # Saving config
        self.tf_suffix = ft.TextField(
            label="Κατάληξη Αρχείου Εξαγωγής",
            value="_nobg",
            text_size=12,
            height=45,
            bgcolor="#1A261F",
            border_color="#2D3F34",
            on_change=self.on_setting_changed
        )
        
        self.switch_overwrite = ft.Switch(
            label="Αντικατάσταση αρχείου αν υπάρχει ήδη",
            value=True,
            on_change=self.on_setting_changed
        )
        
    def build_layout(self):
        # 1. Header Row
        header = ft.Container(
            content=ft.Row(
                controls=[
                    ft.Icon(ft.CupertinoIcons.PHOTO_ON_RECTANGLE, color=ft.Colors.GREEN_400, size=28),
                    ft.Column(
                        controls=[
                            ft.Text("SpyClearBG", size=20, weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                            ft.Text("Αφαίρεση Φόντου με χρήση AI (rembg)", size=11, color=ft.Colors.GREEN_400)
                        ],
                        spacing=0
                    ),
                    ft.VerticalDivider(width=20, color="#2D3F34"),
                    ft.Text("v1.0.5", size=10, color=ft.Colors.GREY_500, weight=ft.FontWeight.W_300),
                    ft.VerticalDivider(width=20, color="#2D3F34"),
                    ft.IconButton(
                        icon=ft.CupertinoIcons.QUESTION_CIRCLE,
                        icon_color=ft.Colors.GREEN_400,
                        on_click=self.show_help_click,
                        tooltip="Οδηγίες Χρήσης & Βοήθεια",
                        icon_size=18
                    ),
                ],
                alignment=ft.MainAxisAlignment.START,
                vertical_alignment=ft.CrossAxisAlignment.CENTER
            ),
            bgcolor="#1A261F",
            padding=ft.Padding(15, 10, 15, 10),
            border_radius=10,
            border=ft.Border.all(1, "#2D3F34"),
            margin=ft.Margin(0, 0, 0, 10)
        )
        
        # 2. Sidebar Layout (Left column)
        sidebar = ft.Container(
            content=ft.Column(
                controls=[
                    # Folder Selection Card
                    ft.Container(
                        content=ft.Column(
                            controls=[
                                ft.Row(controls=[self.btn_select_folder]),
                                ft.Row(controls=[
                                    ft.Icon(ft.CupertinoIcons.FOLDER, size=16, color=ft.Colors.GREEN_400),
                                    self.folder_path_text
                                ]),
                            ],
                            spacing=10
                        ),
                        padding=12,
                        bgcolor="#1A261F",
                        border_radius=10,
                        border=ft.Border.all(1, "#2D3F34")
                    ),
                    
                    # Search and Actions row
                    ft.Row(
                        controls=[self.search_field],
                        spacing=5
                    ),
                    
                    # Check all and Process selected buttons
                    ft.Row(
                        controls=[
                            self.select_all_checkbox,
                            self.btn_process_selected
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    
                    # Scrollable images list container
                    ft.Text("Αρχεία Εικόνων:", size=12, color=ft.Colors.GREY_400, weight=ft.FontWeight.BOLD),
                    ft.Container(
                        content=self.images_list_container,
                        expand=True,
                        border_radius=10,
                    )
                ],
                spacing=10
            ),
            width=380,
            padding=0
        )
        
        # 3. Preview Tab View
        tab_preview = ft.Column(
            controls=[
                ft.Row(
                    controls=[
                        ft.Column(controls=[self.original_preview_title, self.original_preview_container], expand=True),
                        ft.Column(controls=[self.processed_preview_title, self.processed_preview_container], expand=True),
                    ],
                    expand=True,
                    spacing=15
                ),
                ft.Container(
                    content=ft.Row(
                        controls=[
                            self.btn_process_current,
                            ft.Row(
                                controls=[
                                    self.btn_open_file,
                                    self.btn_view_result,
                                    self.btn_delete_result
                                ],
                                spacing=5
                            )
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    ),
                    padding=ft.Padding(0, 10, 0, 10)
                )
            ],
            expand=True
        )
        
        # 4. Settings Tab View
        tab_settings = ft.Container(
            content=ft.Column(
                controls=[
                    ft.Text("Παράμετροι rembg", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                    self.dropdown_model,
                    ft.Divider(color="#2D3F34", height=10),
                    self.switch_alpha_matting,
                    self.alpha_sliders_container,
                    ft.Divider(color="#2D3F34", height=10),
                    ft.Row(controls=[self.switch_only_mask, self.switch_post_process], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(color="#2D3F34", height=10),
                    self.switch_custom_bg,
                    self.color_picker_container,
                    ft.Divider(color="#2D3F34", height=10),
                    ft.Text("Ρυθμίσεις Αποθήκευσης", size=14, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                    self.tf_suffix,
                    self.switch_overwrite,
                ],
                scroll=ft.ScrollMode.ALWAYS,
                spacing=15
            ),
            padding=15,
            bgcolor="#1A261F",
            border_radius=10,
            border=ft.Border.all(1, "#2D3F34")
        )
        
        # Tabs control to switch between Preview and Settings
        tabs = ft.Tabs(
            length=2,
            expand=True,
            content=ft.Column(
                expand=True,
                controls=[
                    ft.TabBar(
                        tabs=[
                            ft.Tab(label="Προεπισκόπηση & Επεξεργασία", icon=ft.CupertinoIcons.PHOTO),
                            ft.Tab(label="Ρυθμίσεις RemBG", icon=ft.CupertinoIcons.SETTINGS),
                        ]
                    ),
                    ft.TabBarView(
                        expand=True,
                        controls=[
                            tab_preview,
                            tab_settings
                        ]
                    )
                ]
            )
        )
        
        # Horizontal layout including Sidebar and Tabs/Preview
        main_content = ft.Row(
            controls=[
                sidebar,
                ft.VerticalDivider(width=15, color="#2D3F34"),
                tabs
            ],
            expand=True,
            spacing=0
        )
        
        # 5. Footer Row
        footer = ft.Container(
            content=ft.Column(
                controls=[
                    self.progress_bar,
                    ft.Row(
                        controls=[
                            self.status_text,
                            ft.Text("SpyClearBG - AI Powered", size=10, color=ft.Colors.GREY_500)
                        ],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN
                    )
                ],
                spacing=5
            ),
            bgcolor="#1A261F",
            padding=ft.Padding(10, 10, 10, 10),
            border_radius=10,
            border=ft.Border.all(1, "#2D3F34"),
            margin=ft.Margin(0, 10, 0, 0)
        )
        
        # Add components to Page
        self.page.add(
            ft.Column(
                controls=[
                    header,
                    main_content,
                    footer
                ],
                expand=True
            )
        )
        
    # State Helpers
    def safe_update(self, control):
        if control and control.page:
            try:
                control.update()
            except Exception:
                pass
                
    def safe_page_update(self):
        if self.page:
            try:
                self.page.update()
                # Εκβιασμός Repaint στο Windows Desktop: αλλάζουμε το πλάτος κατά 1px για να εξαναγκάσουμε τον Flutter client να κάνει redraw
                if not self.page.web:
                    current_width = self.page.window_width
                    if current_width:
                        self.page.window_width = current_width + 1
                        self.page.update()
                        self.page.window_width = current_width
                        self.page.update()
            except Exception:
                pass
                
    def log_message(self, message):
        self.status_text.value = message
        self.safe_update(self.status_text)
        
    def show_snake_bar(self, message):
        snack = ft.SnackBar(ft.Text(message, color=ft.Colors.WHITE), bgcolor=ft.Colors.GREEN_800)
        self.page.overlay.append(snack)
        snack.open = True
        self.page.update()
        
    def show_help_click(self, e):
        help_content = ft.Column(
            controls=[
                ft.Text("SpyClearBG - Οδηγίες Χρήσης", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.GREEN_400),
                ft.Text(
                    "Η εφαρμογή αυτή αφαιρεί αυτόματα το φόντο από φωτογραφίες χρησιμοποιώντας "
                    "μοντέλα Τεχνητής Νοημοσύνης (rembg).\n",
                    size=12
                ),
                ft.Text("Βήματα Λειτουργίας:", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.WHITE),
                ft.Text(
                    "1. Πατήστε 'Επιλογή Φακέλου' για να επιλέξετε τον κατάλογο με τις εικόνες σας.\n"
                    "2. Επιλέξτε μια εικόνα από τη λίστα στα αριστερά για side-by-side προεπισκόπηση.\n"
                    "3. Ρυθμίστε τις παραμέτρους (μοντέλο AI, Alpha Matting, χρώμα φόντου) στην καρτέλα 'Ρυθμίσεις RemBG' αν χρειάζεται.\n"
                    "4. Πατήστε 'Έναρξη Αφαίρεσης Φόντου' για τη συγκεκριμένη εικόνα, ή χρησιμοποιήστε τα Checkboxes και πατήστε 'Αφαίρεση στα Επιλεγμένα' για ομαδική επεξεργασία.\n"
                    "5. Οι επεξεργασμένες εικόνες αποθηκεύονται στον ίδιο φάκελο με την κατάληξη '_nobg.png'.",
                    size=12
                ),
                ft.Divider(color="#2D3F34", height=15),
                ft.Text("Επεξήγηση Μοντέλων AI:", weight=ft.FontWeight.BOLD, size=13, color=ft.Colors.WHITE),
                ft.Text(
                    "- u2net: Το προεπιλεγμένο μοντέλο γενικής χρήσης.\n"
                    "- u2netp: Ελαφρύ/γρήγορο μοντέλο για συσκευές με χαμηλούς πόρους.\n"
                    "- u2net_human_seg: Εξειδικευμένο για ανθρώπινες φιγούρες.\n"
                    "- u2net_cloth_seg: Εξειδικευμένο για ρούχα και ενδύματα.\n"
                    "- siluela: Εξειδικευμένο για σιλουέτες και προϊόντα.\n"
                    "- isnet-general-use: Νέο μοντέλο γενικής χρήσης υψηλής ακρίβειας.\n"
                    "- isnet-anime: Εξειδικευμένο για anime / σκίτσα.",
                    size=11
                ),
                ft.Divider(color="#2D3F34", height=15),
                ft.Text(
                    spans=[
                        ft.TextSpan("Έκδοση: v1.0.5 (build 6) | "),
                        ft.TextSpan(
                            "Δημιουργός: spyalekos",
                            url="https://github.com/spyalekos",
                            style=ft.TextStyle(color=ft.Colors.GREEN_400, decoration=ft.TextDecoration.UNDERLINE)
                        ),
                        ft.TextSpan(" | Δημιουργήθηκε με Flet & rembg.")
                    ],
                    size=10,
                    italic=True,
                    color=ft.Colors.GREY_500
                )
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
            height=400
        )
        
        close_btn = ft.TextButton("Κλείσιμο", on_click=self.close_help_dialog)
        self.help_dialog = ft.AlertDialog(
            content=help_content,
            actions=[close_btn],
            actions_alignment=ft.MainAxisAlignment.END
        )
        self.page.show_dialog(self.help_dialog)

    def close_help_dialog(self, e):
        self.page.pop_dialog()
        
    def get_file_size_str(self, path):
        try:
            bytes_size = os.path.getsize(path)
            if bytes_size < 1024:
                return f"{bytes_size} B"
            elif bytes_size < 1024 * 1024:
                return f"{bytes_size / 1024:.1f} KB"
            else:
                return f"{bytes_size / (1024 * 1024):.1f} MB"
        except Exception:
            return "N/A"
            
    # Event Handlers & Core Logic
    async def select_folder_click(self, e):
        path = await self.file_picker.get_directory_path(dialog_title="Επιλέξτε φάκελο με φωτογραφίες")
        if not path:
            self.log_message("Ακυρώθηκε η επιλογή φακέλου.")
            return
            
        self.folder_path = path
        self.folder_path_text.value = path
        self.folder_path_text.italic = False
        self.folder_path_text.color = ft.Colors.WHITE
        self.safe_update(self.folder_path_text)
        
        self.log_message(f"Σάρωση φακέλου: {path}")
        self.scan_and_load_folder()
        
    def scan_and_load_folder(self):
        if not self.folder_path or not os.path.exists(self.folder_path):
            self.log_message("Σφάλμα: Ο φάκελος δεν υπάρχει.")
            return
            
        # Φιλτράρισμα αρχείων εικόνων
        extensions = ('*.jpg', '*.jpeg', '*.png', '*.webp', '*.bmp', '*.JPG', '*.JPEG', '*.PNG', '*.WEBP', '*.BMP')
        all_files = []
        for ext in extensions:
            all_files.extend(glob.glob(os.path.join(self.folder_path, ext)))
            
        # Αφαίρεση διπλότυπων (λόγω Windows paths case-insensitivity)
        all_files = list(set(os.path.abspath(f) for f in all_files))
        all_files.sort()
        
        suffix = self.settings["save_suffix"]
        
        self.image_files = []
        for filepath in all_files:
            filename = os.path.basename(filepath)
            
            # Αγνοούμε εικόνες αποτελεσμάτων (που έχουν ήδη το suffix)
            if filename.lower().endswith(f"{suffix.lower()}.png"):
                continue
                
            # Έλεγχος αν υπάρχει ήδη έτοιμο αποτέλεσμα
            base, _ = os.path.splitext(filepath)
            result_path = f"{base}{suffix}.png"
            exists = os.path.exists(result_path)
            
            self.image_files.append({
                "name": filename,
                "path": filepath,
                "selected": False,
                "status": "Επεξεργάστηκε" if exists else "Εκκρεμεί",
                "result_path": result_path if exists else None
            })
            
        self.selected_index = -1
        self.select_all_checkbox.value = False
        self.safe_update(self.select_all_checkbox)
        
        # Φόρτωμα λίστας στην οθόνη
        self.build_images_list_ui()
        self.show_blank_preview()
        
        total_found = len(self.image_files)
        self.log_message(f"Βρέθηκαν {total_found} εικόνες στο φάκελο.")
        
        # Αυτόματη επιλογή της πρώτης εικόνας αν υπάρχει
        if total_found > 0:
            self.select_image_for_preview(0)
            
    def build_images_list_ui(self):
        self.images_list_container.controls.clear()
        
        search_query = self.search_field.value.lower() if self.search_field.value else ""
        
        for index, item in enumerate(self.image_files):
            # Φιλτράρισμα βάσει αναζήτησης
            if search_query and search_query not in item["name"].lower():
                continue
                
            status = item["status"]
            if status == "Επεξεργάστηκε":
                status_icon = ft.CupertinoIcons.CHECKMARK_CIRCLE_FILL
                status_color = ft.Colors.GREEN
                status_text = "Ολοκληρώθηκε"
            elif status == "Επεξεργασία...":
                status_icon = None
                status_color = ft.Colors.ORANGE
                status_text = "Επεξεργασία..."
            elif status == "Σφάλμα":
                status_icon = ft.CupertinoIcons.EXCLAMATIONMARK_TRIANGLE_FILL
                status_color = ft.Colors.RED
                status_text = "Σφάλμα"
            else:
                status_icon = ft.CupertinoIcons.PHOTO
                status_color = ft.Colors.GREY_600
                status_text = "Εκκρεμεί"
                
            if status_icon:
                status_control = ft.Icon(status_icon, color=status_color, size=20)
            else:
                status_control = ft.ProgressRing(width=16, height=16, stroke_width=2, color=ft.Colors.ORANGE)
                
            is_selected = (index == self.selected_index)
            
            # Δημιουργία checkbox με κλειστό closure
            chk = ft.Checkbox(
                value=item["selected"],
                on_change=self.make_toggle_handler(index),
                fill_color={"": ft.Colors.GREEN}
            )
            
            # Build individual play button
            if status == "Επεξεργασία...":
                action_btn = ft.IconButton(
                    icon=ft.CupertinoIcons.ARROW_COUNTERCLOCKWISE,
                    icon_color=ft.Colors.RED,
                    disabled=True
                )
            else:
                action_btn = ft.IconButton(
                    icon=ft.CupertinoIcons.PLAY_FILL,
                    icon_color=ft.Colors.GREEN_400,
                    tooltip="Αφαίρεση φόντου από αυτή την εικόνα",
                    on_click=self.make_process_handler(index)
                )
                
            card_content = ft.Container(
                content=ft.Row(
                    controls=[
                        chk,
                        status_control,
                        ft.GestureDetector(
                            content=ft.Column(
                                controls=[
                                    ft.Text(
                                        item["name"],
                                        size=13,
                                        weight=ft.FontWeight.W_500,
                                        color=ft.Colors.WHITE if is_selected else ft.Colors.GREY_300,
                                        max_lines=1,
                                        overflow=ft.TextOverflow.ELLIPSIS
                                    ),
                                    ft.Text(
                                        f"{self.get_file_size_str(item['path'])} | {status_text}",
                                        size=11,
                                        color=ft.Colors.GREEN_400 if is_selected else ft.Colors.GREY_500
                                    )
                                ],
                                spacing=2,
                                expand=True
                            ),
                            on_tap=self.make_select_handler(index),
                            expand=True
                        ),
                        action_btn
                    ],
                    spacing=5,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER
                ),
                padding=ft.Padding(6, 6, 6, 6),
                border_radius=8,
                bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN) if is_selected else "#1E2D24" if status == "Επεξεργάστηκε" else "#1A261F",
                border=ft.Border.all(1, ft.Colors.GREEN_600 if is_selected else "#2D3F34"),
                margin=ft.Margin(0, 0, 0, 5)
            )
            
            self.images_list_container.controls.append(card_content)
            
        self.safe_update(self.images_list_container)
        
    # Helper closures for event loops
    def make_toggle_handler(self, idx):
        return lambda e: self.toggle_image_select(idx, e.control.value)
        
    def make_process_handler(self, idx):
        return lambda _: self.process_image_index(idx)
        
    def make_select_handler(self, idx):
        return lambda _: self.select_image_for_preview(idx)
        
    def toggle_image_select(self, index, value):
        self.image_files[index]["selected"] = value
        all_selected = all(item["selected"] for item in self.image_files)
        self.select_all_checkbox.value = all_selected
        self.safe_update(self.select_all_checkbox)
        
    def toggle_select_all(self, value):
        for item in self.image_files:
            item["selected"] = value
        self.build_images_list_ui()
        
    def select_image_for_preview(self, index):
        self.selected_index = index
        self.build_images_list_ui()
        self.load_previews()
        
    def load_previews(self):
        if self.selected_index < 0 or self.selected_index >= len(self.image_files):
            self.show_blank_preview()
            return
            
        item = self.image_files[self.selected_index]
        
        # 1. Φόρτωμα Αρχικής Εικόνας
        self.log_message(f"Φόρτωση προεπισκόπησης για: {item['name']}...")
        orig_bytes = get_image_bytes(item["path"])
        if orig_bytes:
            # Δημιουργούμε νέο Image control για να εξαναγκάσουμε τον Flutter client να κάνει redraw
            self.original_preview_image = ft.Image(src=orig_bytes, fit="contain")
            self.original_preview_title.value = f"Αρχική ({item['name']})"
            self.original_preview_container.content = self.original_preview_image
        else:
            self.original_preview_container.content = ft.Text("Αδυναμία φόρτωσης αρχικής εικόνας", color=ft.Colors.RED_400)
            
        # 2. Φόρτωμα Αποτελέσματος (αν υπάρχει)
        suffix = self.settings["save_suffix"]
        base, _ = os.path.splitext(item["path"])
        result_path = f"{base}{suffix}.png"
        
        if os.path.exists(result_path):
            item["status"] = "Επεξεργάστηκε"
            item["result_path"] = result_path
            res_bytes = get_image_bytes(result_path)
            if res_bytes:
                # Δημιουργούμε νέο Image control για να εξαναγκάσουμε τον Flutter client να κάνει redraw
                self.processed_preview_image = ft.Image(src=res_bytes, fit="contain")
                self.processed_preview_title.value = f"Αποτέλεσμα ({os.path.basename(result_path)})"
                self.processed_preview_container.content = self.processed_preview_image
            else:
                self.processed_preview_container.content = ft.Text("Αδυναμία φόρτωσης αποτελέσματος", color=ft.Colors.RED_400)
            self.btn_delete_result.visible = True
            self.btn_view_result.visible = True
        else:
            self.processed_preview_title.value = "Αποτέλεσμα"
            self.processed_preview_container.content = ft.Column(
                controls=[
                    ft.Icon(ft.CupertinoIcons.PHOTO, size=60, color=ft.Colors.GREY_600),
                    ft.Text("Εκκρεμεί η αφαίρεση φόντου", size=14, color=ft.Colors.GREY_500, text_align=ft.TextAlign.CENTER)
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER
            )
            self.btn_delete_result.visible = False
            self.btn_view_result.visible = False
            
        self.btn_process_current.disabled = False
        self.btn_open_file.disabled = False
        
        self.safe_page_update()
        self.log_message(f"Προβολή: {item['name']}")
        
    def show_blank_preview(self):
        self.original_preview_title.value = "Αρχική Εικόνα"
        self.original_preview_container.content = ft.Column(
            controls=[
                ft.Icon(ft.CupertinoIcons.PHOTO, size=60, color=ft.Colors.GREY_600),
                ft.Text("Επιλέξτε μια εικόνα από τη λίστα", size=14, color=ft.Colors.GREY_500)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        self.processed_preview_title.value = "Αποτέλεσμα"
        self.processed_preview_container.content = ft.Column(
            controls=[
                ft.Icon(ft.CupertinoIcons.PHOTO, size=60, color=ft.Colors.GREY_600),
                ft.Text("Το αποτέλεσμα θα εμφανιστεί εδώ", size=14, color=ft.Colors.GREY_500)
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER
        )
        
        self.btn_process_current.disabled = True
        self.btn_open_file.disabled = True
        self.btn_delete_result.visible = False
        self.btn_view_result.visible = False
        
        self.safe_page_update()
        
    # RemBG Processing Functions
    def get_rembg_session(self, model_name):
        if model_name not in self.sessions:
            self.log_message(f"Αρχικοποίηση/Λήψη μοντέλου {model_name} (αυτό γίνεται μόνο την 1η φορά)...")
            self.sessions[model_name] = rembg.new_session(model_name)
        return self.sessions[model_name]
        
    def process_image_core(self, index):
        item = self.image_files[index]
        
        # Έλεγχος αν το αρχείο υπάρχει ακόμα
        if not os.path.exists(item["path"]):
            item["status"] = "Σφάλμα"
            self.log_message(f"Σφάλμα: Το αρχείο {item['name']} δεν βρέθηκε.")
            return
            
        item["status"] = "Επεξεργασία..."
        self.build_images_list_ui()
        
        model_name = self.settings["model_name"]
        
        try:
            # Λήψη του session (ίσως πάρει χρόνο)
            session = self.get_rembg_session(model_name)
            
            self.log_message(f"Επεξεργασία αφαίρεσης φόντου: {item['name']}...")
            
            # Άνοιγμα εικόνας με PIL
            img = Image.open(item["path"])
            # Διόρθωση EXIF προσανατολισμού
            img = ImageOps.exif_transpose(img)
            
            # Δημιουργία παραμέτρων
            remove_args = {
                "session": session,
                "alpha_matting": self.settings["alpha_matting"],
                "alpha_matting_foreground_threshold": int(self.settings["alpha_matting_foreground_threshold"]),
                "alpha_matting_background_threshold": int(self.settings["alpha_matting_background_threshold"]),
                "alpha_matting_erode_size": int(self.settings["alpha_matting_erode_size"]),
                "only_mask": self.settings["only_mask"],
                "post_process_mask": self.settings["post_process_mask"],
            }
            
            if self.settings["custom_bg"]:
                bg_color = (
                    int(self.settings["bg_color_r"]),
                    int(self.settings["bg_color_g"]),
                    int(self.settings["bg_color_b"]),
                    int(self.settings["bg_color_a"])
                )
                remove_args["bgcolor"] = bg_color
                
            # Εκτέλεση αφαίρεσης φόντου
            out_img = rembg.remove(img, **remove_args)
            
            # Αποθήκευση
            suffix = self.settings["save_suffix"]
            base, _ = os.path.splitext(item["path"])
            out_path = f"{base}{suffix}.png"
            
            # Έλεγχος overwrite
            if os.path.exists(out_path) and not self.settings["overwrite"]:
                # Αν δεν θέλουμε overwrite, προσθέτουμε timestamp ή μετρητή
                import time
                out_path = f"{base}{suffix}_{int(time.time())}.png"
                
            out_img.save(out_path, "PNG")
            
            item["status"] = "Επεξεργάστηκε"
            item["result_path"] = out_path
            self.log_message(f"Επιτυχής επεξεργασία: {item['name']}")
        except Exception as e:
            item["status"] = "Σφάλμα"
            self.log_message(f"Σφάλμα στο αρχείο {item['name']}: {str(e)}")
            print(f"Error processing {item['name']}: {e}")
            
        self.build_images_list_ui()
        
        # Αν είναι η τρέχουσα επιλεγμένη εικόνα, ανανεώνουμε την προεπισκόπηση
        if index == self.selected_index:
            self.load_previews()
            
    def process_image_index(self, index):
        if index < 0 or index >= len(self.image_files):
            return
            
        if self.processing:
            self.show_snake_bar("Γίνεται ήδη επεξεργασία. Παρακαλώ περιμένετε.")
            return
            
        self.processing = True
        self.progress_bar.visible = True
        self.progress_bar.value = None # Indeterminate loading
        self.safe_update(self.progress_bar)
        
        def run_thread():
            try:
                self.process_image_core(index)
            finally:
                self.processing = False
                self.progress_bar.visible = False
                self.safe_update(self.progress_bar)
                self.show_snake_bar("Η επεξεργασία ολοκληρώθηκε!")
                
        self.page.run_thread(run_thread)
        
    def start_bulk_processing(self):
        if self.processing:
            self.show_snake_bar("Γίνεται ήδη επεξεργασία. Παρακαλώ περιμένετε.")
            return
            
        selected_indices = [idx for idx, item in enumerate(self.image_files) if item["selected"]]
        if not selected_indices:
            self.show_snake_bar("Δεν έχετε επιλέξει καμία εικόνα με το Checkbox!")
            return
            
        self.processing = True
        self.progress_bar.visible = True
        self.progress_bar.value = 0.0
        self.safe_update(self.progress_bar)
        
        def run_bulk_thread():
            total = len(selected_indices)
            try:
                for count, idx in enumerate(selected_indices):
                    self.progress_bar.value = count / total
                    self.safe_update(self.progress_bar)
                    self.process_image_core(idx)
                    
                self.progress_bar.value = 1.0
                self.safe_update(self.progress_bar)
                self.log_message(f"Η ομαδική επεξεργασία ολοκληρώθηκε για {total} αρχεία.")
                self.show_snake_bar(f"Ολοκληρώθηκε η επεξεργασία {total} εικόνων!")
            except Exception as ex:
                self.log_message(f"Σφάλμα κατά την ομαδική επεξεργασία: {ex}")
            finally:
                self.processing = False
                self.progress_bar.visible = False
                self.safe_update(self.progress_bar)
                
        self.page.run_thread(run_bulk_thread)
        
    # File Operations (Open, Delete)
    def open_current_file(self):
        if self.selected_index < 0 or self.selected_index >= len(self.image_files):
            return
        filepath = self.image_files[self.selected_index]["path"]
        try:
            if os.path.exists(filepath):
                # Χρήση os.startfile για Windows
                os.startfile(filepath)
                self.log_message(f"Άνοιγμα αρχείου: {os.path.basename(filepath)}")
        except Exception as e:
            self.show_snake_bar(f"Αδυναμία ανοίγματος αρχείου: {e}")
            
    def view_processed_file(self):
        if self.selected_index < 0 or self.selected_index >= len(self.image_files):
            return
        result_path = self.image_files[self.selected_index]["result_path"]
        try:
            if result_path and os.path.exists(result_path):
                os.startfile(result_path)
                self.log_message(f"Άνοιγμα αποτελέσματος: {os.path.basename(result_path)}")
        except Exception as e:
            self.show_snake_bar(f"Αδυναμία ανοίγματος αποτελέσματος: {e}")
            
    def delete_processed_file(self):
        if self.selected_index < 0 or self.selected_index >= len(self.image_files):
            return
        item = self.image_files[self.selected_index]
        result_path = item["result_path"]
        try:
            if result_path and os.path.exists(result_path):
                os.remove(result_path)
                item["result_path"] = None
                item["status"] = "Εκκρεμεί"
                self.log_message(f"Διαγράφηκε το αποτέλεσμα: {os.path.basename(result_path)}")
                self.build_images_list_ui()
                self.load_previews()
                self.show_snake_bar("Το αποτέλεσμα διαγράφηκε με επιτυχία.")
        except Exception as e:
            self.show_snake_bar(f"Αδυναμία διαγραφής αρχείου: {e}")
            
    # Settings & Toggles Event Handlers
    def on_alpha_matting_toggled(self, e):
        val = e.control.value
        self.settings["alpha_matting"] = val
        self.alpha_sliders_container.visible = val
        self.safe_update(self.alpha_sliders_container)
        
    def on_custom_bg_toggled(self, e):
        val = e.control.value
        self.settings["custom_bg"] = val
        self.color_picker_container.visible = val
        self.safe_update(self.color_picker_container)
        
    def on_color_changed(self, e):
        r = int(self.slider_r.value)
        g = int(self.slider_g.value)
        b = int(self.slider_b.value)
        a = int(self.slider_a.value)
        
        self.settings["bg_color_r"] = r
        self.settings["bg_color_g"] = g
        self.settings["bg_color_b"] = b
        self.settings["bg_color_a"] = a
        
        # Flutter/Flet Hex Format: #AARRGGBB
        hex_color = f"#{a:02x}{r:02x}{g:02x}{b:02x}"
        self.color_preview_box.bgcolor = hex_color
        self.safe_update(self.color_preview_box)
        
    def on_setting_changed(self, e):
        # Ενημέρωση των settings βάσει των UI controls
        self.settings["model_name"] = self.dropdown_model.value
        self.settings["alpha_matting_foreground_threshold"] = self.slider_fg.value
        self.settings["alpha_matting_background_threshold"] = self.slider_bg.value
        self.settings["alpha_matting_erode_size"] = self.slider_erode.value
        self.settings["only_mask"] = self.switch_only_mask.value
        self.settings["post_process_mask"] = self.switch_post_process.value
        self.settings["save_suffix"] = self.tf_suffix.value
        self.settings["overwrite"] = self.switch_overwrite.value

def main(page: ft.Page):
    # Ρύθμιση παραθύρου
    page.title = "SpyClearBG - Αφαίρεση Φόντου"
    page.window_width = 1200
    page.window_height = 820
    page.window_min_width = 1000
    page.window_min_height = 700
    page.window_resizable = True
    
    # Ρύθμιση Θέματος (Dark green theme σύμφωνα με instructions.md)
    page.theme_mode = ft.ThemeMode.DARK
    page.theme = ft.Theme(
        color_scheme=ft.ColorScheme(
            primary="#4CAF50",             # Accent: Material Green 500
            primary_container="#1A261F",   # Surface dark green-gray
            surface="#1A261F",             # Surface panels
            on_primary=ft.Colors.WHITE,
            on_surface=ft.Colors.WHITE,
            secondary="#4CAF50",
            on_secondary=ft.Colors.WHITE,
        )
    )
    
    # Αλλαγή του default background color της σελίδας
    page.bgcolor = "#0A140E"
    
    # Αρχικοποίηση της εφαρμογής
    app = SpyClearBGApp(page)
    app.build_layout()
    page.update()
    
    # Κλείσιμο του PyInstaller Splash Screen (αν υπάρχει)
    try:
        import pyi_splash
        pyi_splash.close()
    except ImportError:
        pass

if __name__ == "__main__":
    ft.run(main)
