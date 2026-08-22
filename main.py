import threading
import requests
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle

# ============ CONFIGURACION ============
TELEGRAM_BOT_TOKEN = "7661276868:AAFrh_0DBhp41Tneh653xBurBKZ3qZau0nI"
TELEGRAM_CHAT_ID = "7284263338"
NOMBRE_CONTACTO = "Chuchito"       # Debe coincidir EXACTO con el nombre guardado en Contactos
TIPO_LLAMADA = "video"             # "video" o "audio"

# Emisoras disponibles por voz. Agrega mas copiando el mismo formato.
# La CLAVE es la palabra que tu papa debe decir para elegirla.
ESTACIONES = {
    "guasca": "https://video2.getstreamhosting.com:2020/stream/8000",
    "uno": "https://playerservices.streamtheworld.com/api/livestream-redirect/RADIO_1_BOGAAC.aac",
    # "nombre_emisora_3": "URL_AQUI",
    # "nombre_emisora_4": "URL_AQUI",
}
EMISORA_POR_DEFECTO = "guasca"

BATTERY_UMBRAL = 15                    # % de batería para avisar
BATTERY_CHECK_SEGUNDOS = 300           # cada cuánto revisa (5 minutos)
# =========================================

WAKE_WORD = "chuchito"


def enviar_telegram(texto):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={
            "chat_id": TELEGRAM_CHAT_ID,
            "text": f"Tu papá dice:\n\n\"{texto}\""
        }, timeout=15)
    except Exception as e:
        print(f"Error enviando a Telegram: {e}")


def lanzar_llamada_whatsapp(nombre_contacto, video=True):
    """Busca al contacto en la agenda de Android y dispara llamada/videollamada de WhatsApp."""
    from jnius import autoclass
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    ContactsData = autoclass('android.provider.ContactsContract$Data')
    Intent = autoclass('android.content.Intent')
    activity = PythonActivity.mActivity
    resolver = activity.getContentResolver()

    mimetype = "vnd.android.cursor.item/vnd.com.whatsapp.video.call" if video \
        else "vnd.android.cursor.item/vnd.com.whatsapp.voip.call"

    selection = f"{ContactsData.MIMETYPE} = ? AND {ContactsData.DISPLAY_NAME} = ?"
    selection_args = [mimetype, nombre_contacto]

    cursor = resolver.query(ContactsData.CONTENT_URI, None, selection, selection_args, None)

    if cursor is not None and cursor.moveToFirst():
        id_col = cursor.getColumnIndex(ContactsData._ID)
        data_id = cursor.getLong(id_col)
        cursor.close()

        Uri = autoclass('android.net.Uri')
        uri = Uri.withAppendedPath(ContactsData.CONTENT_URI, str(data_id))
        intent = Intent(Intent.ACTION_VIEW)
        intent.setDataAndType(uri, mimetype)
        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
        activity.startActivity(intent)
        return True
    else:
        if cursor is not None:
            cursor.close()
        print(f"No se encontró un botón de llamada WhatsApp para '{nombre_contacto}'.")
        return False


def ajustar_volumen(subir=True):
    from jnius import autoclass, cast
    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Context = autoclass('android.content.Context')
    AudioManager = autoclass('android.media.AudioManager')
    activity = PythonActivity.mActivity
    audio_manager = cast('android.media.AudioManager', activity.getSystemService(Context.AUDIO_SERVICE))
    direction = AudioManager.ADJUST_RAISE if subir else AudioManager.ADJUST_LOWER
    audio_manager.adjustStreamVolume(AudioManager.STREAM_MUSIC, direction, AudioManager.FLAG_SHOW_UI)


class Radio:
    """Controla la reproducción de radio por internet usando MediaPlayer de Android."""

    def __init__(self):
        self.mediaplayer = None
        self.reproduciendo = False
        self.emisora_actual = EMISORA_POR_DEFECTO
        self._listener_ref = None

    def reproducir(self, nombre_emisora=None):
        from android.runnable import run_on_ui_thread
        from jnius import autoclass, PythonJavaClass, java_method

        if nombre_emisora and nombre_emisora in ESTACIONES:
            self.emisora_actual = nombre_emisora

        url = ESTACIONES.get(self.emisora_actual)
        if not url:
            return

        MediaPlayer = autoclass('android.media.MediaPlayer')
        AudioManager = autoclass('android.media.AudioManager')

        class OnPrepared(PythonJavaClass):
            __javainterfaces__ = ['android/media/MediaPlayer$OnPreparedListener']
            __javacontext__ = 'app'

            @java_method('(Landroid/media/MediaPlayer;)V')
            def onPrepared(self, mp):
                mp.start()

        @run_on_ui_thread
        def hacer():
            try:
                if self.mediaplayer is not None:
                    self.mediaplayer.stop()
                    self.mediaplayer.release()
            except Exception:
                pass
            self.mediaplayer = MediaPlayer()
            self.mediaplayer.setAudioStreamType(AudioManager.STREAM_MUSIC)
            try:
                self.mediaplayer.setDataSource(url)
                listener = OnPrepared()
                self._listener_ref = listener
                self.mediaplayer.setOnPreparedListener(listener)
                self.mediaplayer.prepareAsync()
                self.reproduciendo = True
            except Exception as e:
                print(f"Error al reproducir radio: {e}")

        hacer()

    def detener(self):
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def hacer():
            try:
                if self.mediaplayer is not None:
                    self.mediaplayer.stop()
                    self.mediaplayer.release()
                    self.mediaplayer = None
            except Exception:
                pass

        hacer()
        self.reproduciendo = False


radio = Radio()


class Voz:
    """Text-to-speech para que la app le hable a tu papá en voz alta."""

    def __init__(self):
        self.tts = None
        self._listener = None
        self._inicializar()

    def _inicializar(self):
        from android.runnable import run_on_ui_thread
        from jnius import autoclass, PythonJavaClass, java_method

        TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')
        Locale = autoclass('java.util.Locale')

        voz = self

        class OnInit(PythonJavaClass):
            __javainterfaces__ = ['android/speech/tts/TextToSpeech$OnInitListener']
            __javacontext__ = 'app'

            @java_method('(I)V')
            def onInit(self, status):
                if status == 0 and voz.tts is not None:
                    voz.tts.setLanguage(Locale('es', 'CO'))

        @run_on_ui_thread
        def crear():
            self._listener = OnInit()
            self.tts = TextToSpeech(PythonActivity.mActivity, self._listener)

        crear()

    def decir(self, texto):
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        TextToSpeech = autoclass('android.speech.tts.TextToSpeech')

        @run_on_ui_thread
        def hacer():
            if self.tts is not None:
                self.tts.speak(texto, TextToSpeech.QUEUE_FLUSH, None, "alerta_bateria")

        hacer()


voz = Voz()


def obtener_estado_bateria():
    """Devuelve (porcentaje, cargando) leyendo el estado real de la batería de Android."""
    from jnius import autoclass

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    Intent = autoclass('android.content.Intent')
    IntentFilter = autoclass('android.content.IntentFilter')
    BatteryManager = autoclass('android.os.BatteryManager')

    activity = PythonActivity.mActivity
    filtro = IntentFilter(Intent.ACTION_BATTERY_CHANGED)
    estado_bateria = activity.registerReceiver(None, filtro)

    if estado_bateria is None:
        return -1, False

    nivel = estado_bateria.getIntExtra(BatteryManager.EXTRA_LEVEL, -1)
    escala = estado_bateria.getIntExtra(BatteryManager.EXTRA_SCALE, -1)
    estado = estado_bateria.getIntExtra(BatteryManager.EXTRA_STATUS, -1)

    porcentaje = int(nivel * 100 / escala) if escala > 0 else -1
    cargando = estado in (BatteryManager.BATTERY_STATUS_CHARGING, BatteryManager.BATTERY_STATUS_FULL)
    return porcentaje, cargando


class MonitorBateria:
    """Revisa la batería periódicamente y avisa por voz + Telegram si está baja."""

    def __init__(self):
        self.ya_avisado_telegram = False

    def revisar(self, dt=None):
        try:
            porcentaje, cargando = obtener_estado_bateria()
        except Exception as e:
            print(f"Error leyendo batería: {e}")
            return

        if porcentaje == -1:
            return

        if cargando or porcentaje > BATTERY_UMBRAL:
            self.ya_avisado_telegram = False
            return

        voz.decir(f"Papá, la batería del celular está baja, en {porcentaje} por ciento. "
                  f"Por favor conéctalo al cargador.")

        if not self.ya_avisado_telegram:
            threading.Thread(
                target=enviar_telegram,
                args=(f"[AVISO] La batería del celular de tu papá está en {porcentaje}% y no se está cargando.",),
                daemon=True
            ).start()
            self.ya_avisado_telegram = True


monitor_bateria = MonitorBateria()


class VoiceEngine:
    """Maneja el ciclo de escucha en ráfagas cortas usando el reconocedor de voz de Android."""

    def __init__(self, on_status, on_transcript):
        self.on_status = on_status
        self.on_transcript = on_transcript
        self.modo_dictado = False
        self._setup()

    def _setup(self):
        from android.runnable import run_on_ui_thread
        from jnius import autoclass, PythonJavaClass, java_method

        SpeechRecognizer = autoclass('android.speech.SpeechRecognizer')
        PythonActivity = autoclass('org.kivy.android.PythonActivity')

        engine = self

        class Listener(PythonJavaClass):
            __javainterfaces__ = ['android/speech/RecognitionListener']
            __javacontext__ = 'app'

            @java_method('(Landroid/os/Bundle;)V')
            def onResults(self, bundle):
                SpeechRecognizerClass = autoclass('android.speech.SpeechRecognizer')
                matches = bundle.getStringArrayList(SpeechRecognizerClass.RESULTS_RECOGNITION)
                texto = matches.get(0) if matches and matches.size() > 0 else ""
                engine._procesar_resultado(texto)

            @java_method('(I)V')
            def onError(self, error):
                engine._reintentar()

            @java_method('(Landroid/os/Bundle;)V')
            def onReadyForSpeech(self, params):
                pass

            @java_method('()V')
            def onBeginningOfSpeech(self):
                pass

            @java_method('(F)V')
            def onRmsChanged(self, rmsdB):
                pass

            @java_method('([B)V')
            def onBufferReceived(self, buffer):
                pass

            @java_method('()V')
            def onEndOfSpeech(self):
                pass

            @java_method('(Landroid/os/Bundle;)V')
            def onPartialResults(self, bundle):
                pass

            @java_method('(ILandroid/os/Bundle;)V')
            def onEvent(self, eventType, params):
                pass

        @run_on_ui_thread
        def crear():
            self.recognizer = SpeechRecognizer.createSpeechRecognizer(PythonActivity.mActivity)
            self.listener = Listener()
            self.recognizer.setRecognitionListener(self.listener)
            self._escuchar()

        crear()

    def _escuchar(self, segundos_extra=False):
        from android.runnable import run_on_ui_thread
        from jnius import autoclass

        RecognizerIntent = autoclass('android.speech.RecognizerIntent')
        Intent = autoclass('android.content.Intent')

        @run_on_ui_thread
        def hacer():
            intent = Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL,
                             RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
            intent.putExtra(RecognizerIntent.EXTRA_LANGUAGE, "es-CO")
            intent.putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, False)
            if segundos_extra:
                intent.putExtra("android.speech.extra.SPEECH_INPUT_COMPLETE_SILENCE_LENGTH_MILLIS", 4000)
                intent.putExtra("android.speech.extra.SPEECH_INPUT_MINIMUM_LENGTH_MILLIS", 2000)
            try:
                self.recognizer.startListening(intent)
            except Exception as e:
                print(f"Error al iniciar escucha: {e}")
                Clock.schedule_once(lambda dt: self._escuchar(), 1)

        self.on_status("Escuchando..." if not self.modo_dictado else "Escuchando lo que dices...")
        hacer()

    def _reintentar(self):
        Clock.schedule_once(lambda dt: self._escuchar(self.modo_dictado), 0.6)

    def _procesar_resultado(self, texto):
        texto_lower = texto.lower().strip()

        if self.modo_dictado:
            self.modo_dictado = False
            if texto_lower:
                self.on_transcript(texto)
                self.on_status(f"Mensaje enviado: \"{texto}\"")
                threading.Thread(target=enviar_telegram, args=(texto,), daemon=True).start()
            Clock.schedule_once(lambda dt: self._escuchar(), 1.5)
            return

        if WAKE_WORD not in texto_lower:
            Clock.schedule_once(lambda dt: self._escuchar(), 0.4)
            return

        # --- Llamar ---
        if "llam" in texto_lower:
            self.on_status(f"Llamando por WhatsApp ({TIPO_LLAMADA})...")
            threading.Thread(
                target=lanzar_llamada_whatsapp,
                args=(NOMBRE_CONTACTO, TIPO_LLAMADA == "video"),
                daemon=True
            ).start()
            Clock.schedule_once(lambda dt: self._escuchar(), 2)

        # --- Mensaje de voz ---
        elif "habl" in texto_lower:
            self.modo_dictado = True
            self.on_status("Dime tu mensaje, te escucho...")
            Clock.schedule_once(lambda dt: self._escuchar(True), 0.3)

        # --- Apagar radio ---
        elif "radio" in texto_lower and any(p in texto_lower for p in ["apaga", "detén", "detener", "para"]):
            self.on_status("Apagando la radio...")
            radio.detener()
            Clock.schedule_once(lambda dt: self._escuchar(), 1.5)

        # --- Volumen ---
        elif "volumen" in texto_lower and "sub" in texto_lower:
            ajustar_volumen(True)
            self.on_status("Subiendo el volumen...")
            Clock.schedule_once(lambda dt: self._escuchar(), 1)

        elif "volumen" in texto_lower and "baj" in texto_lower:
            ajustar_volumen(False)
            self.on_status("Bajando el volumen...")
            Clock.schedule_once(lambda dt: self._escuchar(), 1)

        # --- Encender / cambiar radio ---
        elif "radio" in texto_lower and any(p in texto_lower for p in ["pon", "prende", "enciende"]):
            emisora_pedida = None
            for clave in ESTACIONES:
                if clave in texto_lower:
                    emisora_pedida = clave
                    break
            self.on_status(f"Poniendo la radio: {emisora_pedida or radio.emisora_actual}...")
            radio.reproducir(emisora_pedida)
            Clock.schedule_once(lambda dt: self._escuchar(), 2)

        else:
            Clock.schedule_once(lambda dt: self._escuchar(), 0.4)


class ControlAsistenteApp(App):
    def build(self):
        self.layout = BoxLayout(orientation='vertical', padding=30, spacing=20)

        with self.layout.canvas.before:
            Color(0.05, 0.05, 0.08, 1)
            self.rect = Rectangle(size=self.layout.size, pos=self.layout.pos)
        self.layout.bind(size=self._actualizar_fondo, pos=self._actualizar_fondo)

        self.titulo = Label(
            text="Asistente de Papá",
            font_size=26,
            bold=True,
            size_hint=(1, 0.15)
        )
        self.layout.add_widget(self.titulo)

        self.lbl_estado = Label(
            text="Iniciando...",
            font_size=20,
            size_hint=(1, 0.35)
        )
        self.layout.add_widget(self.lbl_estado)

        self.lbl_ultimo = Label(
            text="",
            font_size=16,
            size_hint=(1, 0.5)
        )
        self.layout.add_widget(self.lbl_ultimo)

        Clock.schedule_once(lambda dt: self._iniciar_motor(), 1)
        Clock.schedule_interval(monitor_bateria.revisar, BATTERY_CHECK_SEGUNDOS)

        return self.layout

    def _actualizar_fondo(self, *args):
        self.rect.size = self.layout.size
        self.rect.pos = self.layout.pos

    def _iniciar_motor(self):
        self.motor = VoiceEngine(
            on_status=self._on_status,
            on_transcript=self._on_transcript
        )

    @mainthread
    def _on_status(self, texto):
        self.lbl_estado.text = texto

    @mainthread
    def _on_transcript(self, texto):
        self.lbl_ultimo.text = texto


if __name__ == '__main__':
    ControlAsistenteApp().run()
