from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.graphics import Color, Rectangle

class ControlAsistenteApp(App):
    def build(self):
        self.estado_actual = "trabajando"
        
        # Estructura visual de tu panel de control
        layout = BoxLayout(orientation='vertical', padding=25, spacing=20)
        
        # Fondo oscuro limpio
        with layout.canvas.before:
            Color(0.1, 0.1, 0.12, 1)
            self.rect = Rectangle(size=(1000, 1000), pos=(0, 0))
            
        # Título
        self.titulo = Label(
            text="PANEL DE CONTROL - PAPÁ",
            font_size=20,
            bold=True,
            size_hint=(1, 0.1)
        )
        layout.add_widget(self.titulo)
        
        # Indicador de tu estado actual
        self.lbl_estado = Label(
            text=f"Tu Estado Actual:\n{self.estado_actual.upper()}",
            font_size=18,
            size_hint=(1, 0.2)
        )
        layout.add_widget(self.lbl_estado)
        
        # Botones para cambiar tu estado a distancia
        btn_disp = Button(text="Cambiar a: DISPONIBLE", background_color=(0.1, 0.6, 0.2, 1))
        btn_disp.bind(on_press=lambda x: self.cambiar_estado("disponible"))
        layout.add_widget(btn_disp)
        
        btn_trab = Button(text="Cambiar a: TRABAJANDO", background_color=(0.8, 0.5, 0.1, 1))
        btn_trab.bind(on_press=lambda x: self.cambiar_estado("trabajando"))
        layout.add_widget(btn_trab)
        
        btn_durm = Button(text="Cambiar a: DURMIENDO", background_color=(0.2, 0.3, 0.7, 1))
        btn_durm.bind(on_press=lambda x: self.cambiar_estado("durmiendo"))
        layout.add_widget(btn_durm)
        
        # Registro de actividad / Alertas recibidas
        self.lbl_log = Label(
            text="Estado de alertas: Sin novedades recientes.",
            font_size=14,
            size_hint=(1, 0.3)
        )
        layout.add_widget(self.lbl_log)
        
        return layout

    def cambiar_estado(self, nuevo_estado):
        self.estado_actual = nuevo_estado
        self.lbl_estado.text = f"Tu Estado Actual:\n{self.estado_actual.upper()}"
        self.lbl_log.text = f"✅ Estado actualizado a '{nuevo_estado}' correctamente."

if __name__ == '__main__':
    ControlAsistenteApp().run()
