import threading
import time
import json
import random
import requests
from datetime import datetime
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.clock import Clock, mainthread
from kivy.graphics import Color, Rectangle

# ============ CONFIGURACION ============
TELEGRAM_BOT_TOKEN = "7661276868:AAFrh_0DBhp41Tneh653xBurBKZ3qZau0nI"

# Un registro por cada familiar que quiera comunicarse con papá.
# - La CLAVE (ej. "chuchito", "maria") es la palabra que tu papá dice para referirse a esa persona.
# - "telegram_chat_id": esa persona debe escribirle una vez a @userinfobot en SU PROPIO Telegram
#   para conseguir su Id, y ponerlo aquí.
# - "nombre_contacto_whatsapp": debe coincidir EXACTO con el nombre guardado en los Contactos
#   del celular de papá (para poder lanzar la videollamada de WhatsApp).
FAMILIARES = {
    "chuchito": {
        "telegram_chat_id": "7284263338",
        "nombre_contacto_whatsapp": "Chuchito",
        "estado": "disponible",
    },
    # "maria": {
    #     "telegram_chat_id": "ID_DE_MARIA_AQUI",
    #     "nombre_contacto_whatsapp": "Maria",
    #     "estado": "disponible",
    # },
}

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

RECORDATORIO_AGUA_SEGUNDOS = 3 * 60 * 60   # cada 3 horas
RECORDATORIOS_AGUA = [
    "Papi, no olvides tomar agua.",
    "Papi, recuerda tomar tu agüita.",
    "Oye papi, un vasito de agua te va a caer bien.",
]

IDLE_MINIMIZAR_SEGUNDOS = 4 * 60        # si no dice "Chuchito" en 4 min, se minimiza
# =========================================

ultima_interaccion = time.time()

WAKE_WORD = "chuchito"                 # nombre del asistente, así lo activa papá
ESTADOS_VALIDOS = {"disponible", "trabajando", "durmiendo", "ocupado"}
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]

_estado_callback = None  # se conecta a la etiqueta en pantalla cuando arranca la app


def reportar_estado(texto):
    """Muestra un mensaje en la pantalla de la app (y en el log) - para ver errores sin necesitar cable USB."""
    print(texto)
    if _estado_callback is not None:
        try:
            _estado_callback(texto)
        except Exception:
            pass


def identificar_familiar(texto_lower):
    """Busca cuál familiar se menciona en el texto; si no menciona a nadie, usa el primero registrado."""
    for clave in FAMILIARES:
        if clave in texto_lower:
            return clave
    return next(iter(FAMILIARES))


def enviar_telegram(chat_id, texto):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        requests.post(url, data={"chat_id": chat_id, "text": texto}, timeout=15)
    except Exception as e:
        reportar_estado(f"ERROR Telegram (mensaje): {e}")


def enviar_audio_telegram(chat_id, ruta_archivo, caption=None):
    """Sube el audio grabado a Telegram como archivo de audio reproducible."""
    if not ruta_archivo:
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendAudio"
        with open(ruta_archivo, 'rb') as f:
            data = {"chat_id": chat_id}
            if caption:
                data["caption"] = caption
            requests.post(url, data=data, files={"audio": f}, timeout=30)
    except Exception as e:
        reportar_estado(f"ERROR Telegram (audio): {e}")


def enviar_menu_telegram(chat_id):
    """Manda los botones táctiles al chat de Telegram de un familiar."""
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        teclado = {
            "keyboard": [
                ["Disponible", "Trabajando"],
                ["Ocupado", "Durmiendo"],
                ["¿Cómo estás, papi?"]
            ],
            "resize_keyboard": True,
            "is_persistent": True
        }
        requests.post(url, data={
            "chat_id": chat_id,
            "text": "Toca un botón para avisarle a tu papá cómo estás, o pregúntale cómo está él:",
            "reply_markup": json.dumps(teclado)
        }, timeout=15)
    except Exception as e:
        reportar_estado(f"ERROR Telegram (menu): {e}")


def grabar_audio(duracion_segundos, callback):
    """Graba el micrófono por 'duracion_segundos' y llama callback(ruta_o_None) al terminar."""
    from android.runnable import run_on_ui_thread
    from jnius import autoclass

    PythonActivity = autoclass('org.kivy.android.PythonActivity')
    MediaRecorder = autoclass('android.media.MediaRecorder')
    AudioSource = autoclass('android.media.MediaRecorder$AudioSource')
    OutputFormat = autoclass('android.media.MediaRecorder$OutputFormat')
    AudioEncoder = autoclass('android.media.MediaRecorder$AudioEncoder')

    activity = PythonActivity.mActivity
    cache_dir = activity.getCacheDir().getAbsolutePath()
    ruta = f"{cache_dir}/mensaje_{int(time.time())}.m4a"

    estado = {"recorder": None}

    @run_on_ui_thread
    def iniciar():
        try:
            rec = MediaRecorder()
            rec.setAudioSource(AudioSource.MIC)
            rec.setOutputFormat(OutputFormat.MPEG_4)
            rec.setAudioEncoder(AudioEncoder.AAC)
            rec.setOutputFile(ruta)
            rec.prepare()
            rec.start()
            estado["recorder"] = rec
        except Exception as e:
            reportar_estado(f"ERROR iniciando grabacion: {e}")

    iniciar()

    def detener(dt):
        @run_on_ui_thread
        def parar():
            rec = estado.get("recorder")
            exito = False
            if rec is not None:
                try:
                    rec.stop()
                    rec.release()
                    exito = True
                except Exception as e:
                    reportar_estado(f"ERROR deteniendo grabacion: {e}")
            callback(ruta if exito else None)

        parar()

    Clock.schedule_once(detener, duracion_segundos)


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
                reportar_estado(f"ERROR radio: {e}")

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

motor_activo = None  # referencia al VoiceEngine, se asigna cuando arranca


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
                    resultado = voz.tts.setLanguage(Locale('es', 'CO'))
                    if resultado < 0:
                        # "es-CO" no está disponible en este motor de voz, usamos español genérico
                        voz.tts.setLanguage(Locale('es'))

        @run_on_ui_thread
        def crear():
            self._listener = OnInit()
            self.tts = TextToSpeech(PythonActivity.mActivity, self._listener)

        crear()

    def decir(self, texto, reanudar_despues=True):
        try:
            from android.runnable import run_on_ui_thread
            from jnius import autoclass

            TextToSpeech = autoclass('android.speech.tts.TextToSpeech')
            HashMap = autoclass('java.util.HashMap')

            if motor_activo is not None:
                motor_activo.pausar()

            @run_on_ui_thread
            def hacer():
                try:
                    if self.tts is not None:
                        # Usamos la versión antigua/simple de speak() (3 argumentos),
                        # la de 4 argumentos con Bundle no se resuelve bien en este pyjnius.
                        self.tts.speak(texto, TextToSpeech.QUEUE_FLUSH, HashMap())
                    else:
                        reportar_estado("ERROR: el motor de voz aún no está listo")
                except Exception as e:
                    reportar_estado(f"ERROR al hablar (speak): {e}")

            hacer()
        except Exception as e:
            reportar_estado(f"ERROR en decir(): {e}")

        if not reanudar_despues:
            return

        # No dependemos de que Android avise cuando termina de hablar (esa función
        # no siempre se dispara en celulares nuevos). Calculamos un tiempo prudente
        # según lo largo del texto, y reanudamos la escucha nosotros mismos.
        duracion_estimada = 1.5 + len(texto.split()) * 0.45
        Clock.schedule_once(lambda dt: _reanudar_escucha(), duracion_estimada)


voz = Voz()


def _reanudar_escucha():
    if motor_activo is not None:
        motor_activo.reanudar()


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
    """Revisa la batería periódicamente y avisa por voz + Telegram (a todos los familiares) si está baja."""

    def __init__(self):
        self.ya_avisado_telegram = False

    def revisar(self, dt=None):
        try:
            porcentaje, cargando = obtener_estado_bateria()
        except Exception as e:
            reportar_estado(f"ERROR bateria: {e}")
            return

        if porcentaje == -1:
            return

        if cargando or porcentaje > BATTERY_UMBRAL:
            self.ya_avisado_telegram = False
            return

        voz.decir(f"Papá, la batería del celular está baja, en {porcentaje} por ciento. "
                  f"Por favor conéctalo al cargador.")

        if not self.ya_avisado_telegram:
            for datos in FAMILIARES.values():
                threading.Thread(
                    target=enviar_telegram,
                    args=(datos["telegram_chat_id"],
                          f"[AVISO] La batería del celular de tu papá está en {porcentaje}% y no se está cargando."),
                    daemon=True
                ).start()
            self.ya_avisado_telegram = True


monitor_bateria = MonitorBateria()


FRASES_ESTADO = {
    "disponible": "está libre, ¿quieres hablar con él? Dile: Chuchito, llámame.",
    "trabajando": "está trabajando en este momento.",
    "ocupado": "está ocupado, te va a llamar en cuanto pueda.",
    "durmiendo": "está durmiendo, mejor no lo molestamos.",
}


def actualizar_estado(persona, nuevo):
    FAMILIARES[persona]["estado"] = nuevo
    frase = FRASES_ESTADO.get(nuevo, f"está {nuevo} ahora.")
    voz.decir(f"Papá, {persona.capitalize()} {frase}")


def responder_hora():
    ahora = datetime.now()
    mes = MESES[ahora.month - 1]
    voz.decir(f"Son las {ahora.hour} horas con {ahora.minute} minutos, "
              f"del día {ahora.day} de {mes} del año {ahora.year}.")


def recordar_agua(dt=None):
    voz.decir(random.choice(RECORDATORIOS_AGUA))


class TelegramEscucha:
    """Revisa cada pocos segundos si algún familiar mandó un mensaje al bot desde su Telegram."""

    def __init__(self, motor):
        self.motor = motor
        self.offset = 0

    def revisar(self, dt=None):
        threading.Thread(target=self._revisar_en_hilo, daemon=True).start()

    def _revisar_en_hilo(self):
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {"offset": self.offset + 1, "timeout": 0}
            resp = requests.get(url, params=params, timeout=15)
            data = resp.json()
            for update in data.get("result", []):
                self.offset = update["update_id"]
                mensaje = update.get("message", {})
                chat_id = str(mensaje.get("chat", {}).get("id", ""))
                texto = (mensaje.get("text") or "").strip()
                if not texto:
                    continue
                persona = self._identificar_por_chat(chat_id)
                if persona is None:
                    continue
                Clock.schedule_once(lambda dt, p=persona, t=texto: self._procesar(p, t), 0)
        except Exception as e:
            reportar_estado(f"ERROR revisando Telegram: {e}")

    def _identificar_por_chat(self, chat_id):
        for persona, datos in FAMILIARES.items():
            if str(datos["telegram_chat_id"]) == chat_id:
                return persona
        return None

    def _procesar(self, persona, texto):
        texto_lower = texto.lower().strip()

        if texto_lower in ("/start", "/menu", "menu"):
            chat_id = FAMILIARES[persona]["telegram_chat_id"]
            threading.Thread(target=enviar_menu_telegram, args=(chat_id,), daemon=True).start()

        elif texto_lower in ESTADOS_VALIDOS:
            actualizar_estado(persona, texto_lower)

        elif "papi" in texto_lower and ("como" in texto_lower or "cómo" in texto_lower):
            self.motor.hacer_pregunta(persona, "¿Cómo estás, papi?")

        else:
            self.motor.hacer_pregunta(persona, texto)


class VoiceEngine:
    """Maneja el ciclo de escucha en ráfagas cortas usando el reconocedor de voz de Android."""

    def __init__(self, on_status, on_transcript):
        self.on_status = on_status
        self.on_transcript = on_transcript
        self.pregunta_pendiente = None
        self.persona_pendiente = None
        self.pausado = False
        self._setup()

    def pausar(self):
        """Detiene el micrófono para que no compita con la voz cuando la app le habla a papá."""
        self.pausado = True
        from android.runnable import run_on_ui_thread

        @run_on_ui_thread
        def hacer():
            try:
                self.recognizer.cancel()
            except Exception:
                pass

        hacer()

    def reanudar(self):
        self.pausado = False
        self._escuchar()

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

    def _escuchar(self):
        if self.pausado:
            return

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
            try:
                self.recognizer.startListening(intent)
            except Exception as e:
                reportar_estado(f"ERROR iniciando escucha: {e}")
                Clock.schedule_once(lambda dt: self._escuchar(), 1)

        self.on_status("Escuchando...")
        hacer()

    def _reintentar(self):
        Clock.schedule_once(lambda dt: self._escuchar(), 0.6)

    def hacer_pregunta(self, persona, texto_pregunta):
        """Llamado cuando un familiar manda una pregunta por Telegram: se la lee a papá y graba su respuesta."""
        try:
            self.persona_pendiente = persona
            self.pregunta_pendiente = texto_pregunta
            self.on_status(f"Preguntando a tu papá de parte de {persona.capitalize()}: \"{texto_pregunta}\"")
            texto_hablado = f"{persona.capitalize()} pregunta: {texto_pregunta}"
            voz.decir(texto_hablado, reanudar_despues=False)
            segundos_espera = 2 + len(texto_hablado.split()) * 0.45
            Clock.schedule_once(lambda dt: self._grabar_mensaje(), segundos_espera)
        except Exception as e:
            reportar_estado(f"ERROR en hacer_pregunta: {e}")
            self.pausado = False
            Clock.schedule_once(lambda dt: self._escuchar(), 2)

    def _grabar_mensaje(self, duracion=10):
        self.on_status("Grabando tu mensaje, habla ahora...")
        grabar_audio(duracion, self._al_terminar_grabacion)

    def _al_terminar_grabacion(self, ruta_archivo):
        self.pausado = False
        persona = self.persona_pendiente or next(iter(FAMILIARES))
        chat_id = FAMILIARES[persona]["telegram_chat_id"]

        if ruta_archivo:
            if self.pregunta_pendiente:
                caption = f"Respuesta de tu papá a: \"{self.pregunta_pendiente}\""
            else:
                caption = "Mensaje de voz de tu papá"
            self.on_status("Mensaje de voz enviado")
            threading.Thread(
                target=enviar_audio_telegram, args=(chat_id, ruta_archivo, caption), daemon=True
            ).start()
        else:
            self.on_status("No se pudo grabar el mensaje, intenta de nuevo")

        self.pregunta_pendiente = None
        self.persona_pendiente = None
        Clock.schedule_once(lambda dt: self._escuchar(), 1.5)

    def _procesar_resultado(self, texto):
        texto_lower = texto.lower().strip()

        if WAKE_WORD not in texto_lower:
            Clock.schedule_once(lambda dt: self._escuchar(), 0.4)
            return

        global ultima_interaccion
        ultima_interaccion = time.time()

        # --- Llamar ---
        if "llam" in texto_lower:
            persona = identificar_familiar(texto_lower)
            datos = FAMILIARES[persona]
            self.on_status(f"Llamando a {persona.capitalize()} por WhatsApp ({TIPO_LLAMADA})...")
            threading.Thread(
                target=lanzar_llamada_whatsapp,
                args=(datos["nombre_contacto_whatsapp"], TIPO_LLAMADA == "video"),
                daemon=True
            ).start()
            Clock.schedule_once(lambda dt: self._escuchar(), 2)

        # --- Mensaje de voz ---
        elif "habl" in texto_lower:
            persona = identificar_familiar(texto_lower)
            self.persona_pendiente = persona
            self.on_status(f"Grabando tu mensaje para {persona.capitalize()}, habla ahora...")
            Clock.schedule_once(lambda dt: self._grabar_mensaje(), 0.5)

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

        # --- Qué hora es ---
        elif "hora" in texto_lower.split() or "horas" in texto_lower.split():
            responder_hora()
            Clock.schedule_once(lambda dt: self._escuchar(), 2)

        # --- Preguntar por el estado de un familiar ---
        elif any(p in texto_lower for p in ["hijo", "hija", "estará", "haciendo"]) or \
                any(nombre in texto_lower for nombre in FAMILIARES):
            persona = identificar_familiar(texto_lower)
            estado_actual = FAMILIARES[persona]["estado"]
            frase = FRASES_ESTADO.get(estado_actual, f"está {estado_actual}.")
            voz.decir(f"{persona.capitalize()} {frase}")
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

        global _estado_callback
        _estado_callback = self._on_status

        Clock.schedule_once(lambda dt: self._pedir_permisos(), 1)
        Clock.schedule_interval(monitor_bateria.revisar, BATTERY_CHECK_SEGUNDOS)
        Clock.schedule_interval(recordar_agua, RECORDATORIO_AGUA_SEGUNDOS)
        Clock.schedule_interval(self._revisar_inactividad, 30)

        return self.layout

    def _revisar_inactividad(self, dt=None):
        if time.time() - ultima_interaccion > IDLE_MINIMIZAR_SEGUNDOS:
            self._minimizar()

    def _minimizar(self):
        try:
            from jnius import autoclass
            PythonActivity = autoclass('org.kivy.android.PythonActivity')
            PythonActivity.mActivity.moveTaskToBack(True)
        except Exception as e:
            reportar_estado(f"ERROR minimizando: {e}")

    def _pedir_permisos(self):
        from android.permissions import request_permissions, Permission
        self._on_status("Pidiendo permisos de micrófono y contactos...")
        request_permissions(
            [Permission.RECORD_AUDIO, Permission.READ_CONTACTS],
            self._al_responder_permisos
        )

    def _al_responder_permisos(self, permisos, resultados):
        if resultados and all(resultados):
            self._iniciar_motor()
        else:
            self._on_status(
                "Faltan permisos. Ve a Ajustes > Apps > Asistente de Papá > Permisos, "
                "y activa Micrófono y Contactos a mano."
            )

    def _actualizar_fondo(self, *args):
        self.rect.size = self.layout.size
        self.rect.pos = self.layout.pos

    def _iniciar_motor(self):
        global motor_activo
        self.motor = VoiceEngine(
            on_status=self._on_status,
            on_transcript=self._on_transcript
        )
        motor_activo = self.motor
        self.telegram_escucha = TelegramEscucha(self.motor)
        Clock.schedule_interval(self.telegram_escucha.revisar, 8)

        for datos in FAMILIARES.values():
            threading.Thread(
                target=enviar_menu_telegram, args=(datos["telegram_chat_id"],), daemon=True
            ).start()

    @mainthread
    def _on_status(self, texto):
        self.lbl_estado.text = texto

    @mainthread
    def _on_transcript(self, texto):
        self.lbl_ultimo.text = texto


if __name__ == '__main__':
    ControlAsistenteApp().run()
