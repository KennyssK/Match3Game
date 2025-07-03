import random
import json
import os

from kivy.app import App
from kivy.uix.gridlayout import GridLayout
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.textinput import TextInput
from kivy.properties import ListProperty, NumericProperty, StringProperty
from kivy.clock import Clock
from kivy.uix.screenmanager import ScreenManager, Screen, FadeTransition
from kivy.animation import Animation
from kivy.uix.scrollview import ScrollView # Добавляем для прокручиваемого текста


# --- Класс GameBoard: Основная логика игры "Три в ряд" ---
class GameBoard:
    def __init__(self, rows, cols, num_types):
        self.rows = rows
        self.cols = cols
        self.num_types = num_types
        self.board = self._create_initial_board()

    def _create_initial_board(self):
        """
        Создаёт начальное игровое поле, заполняя его случайными элементами.
        Гарантирует, что при создании нет совпадений 3-в-ряд.
        """
        board = []
        for r in range(self.rows):
            row = []
            for c in range(self.cols):
                while True:
                    element = random.randint(1, self.num_types)
                    # Проверяем на 3-в-ряд по горизонтали и вертикали, чтобы избежать их при старте
                    if (c >= 2 and row[c-1] == element and row[c-2] == element) or \
                       (r >= 2 and len(board) > r-2 and board[r-1][c] == element and board[r-2][c] == element):
                        continue # Если есть совпадение, генерируем новый элемент
                    else:
                        row.append(element)
                        break # Если совпадений нет, добавляем элемент и переходим к следующему
            board.append(row)
        return board

    def swap_elements(self, r1, c1, r2, c2):
        """
        Меняет местами два элемента на доске, если они соседние.
        Возвращает True, если обмен произошёл успешно, False в противном случае.
        """
        # Проверяем, что элементы соседние (по горизонтали или вертикали)
        if not ((abs(r1 - r2) == 1 and c1 == c2) or \
                (abs(c1 - c2) == 1 and r1 == r2)):
            return False # Несоседние элементы

        # Проверяем, что координаты находятся в пределах доски
        if not (0 <= r1 < self.rows and 0 <= c1 < self.cols and \
                0 <= r2 < self.rows and 0 <= c2 < self.cols):
            return False # Выход за границы доски

        # Выполняем фактический обмен элементами в логической модели доски
        self.board[r1][c1], self.board[r2][c2] = self.board[r2][c2], self.board[r1][c1]
        return True

    def find_matches(self):
        """
        Находит все совпадения (3 или более одинаковых элемента) на доске.
        Возвращает список уникальных координат [(строка, столбец)] всех найденных совпадений.
        """
        matches = set() # Используем set для автоматического исключения дубликатов координат

        # Поиск горизонтальных совпадений
        for r in range(self.rows):
            for c in range(self.cols - 2): # Идём до предпоследнего элемента
                if self.board[r][c] == self.board[r][c+1] == self.board[r][c+2] and self.board[r][c] != 0:
                    for i in range(3):
                        matches.add((r, c + i)) # Добавляем координаты всех трёх элементов совпадения

        # Поиск вертикальных совпадений
        for c in range(self.cols):
            for r in range(self.rows - 2): # Идём до предпоследней строки
                if self.board[r][c] == self.board[r+1][c] == self.board[r+2][c] and self.board[r][c] != 0:
                    for i in range(3):
                        matches.add((r + i, c)) # Добавляем координаты всех трёх элементов совпадения
        return list(matches) # Преобразуем set обратно в список для возврата

    def remove_matches(self, matches):
        """
        Удаляет найденные совпадения, заменяя их на 0 (пустое место).
        Возвращает количество удалённых элементов (очков).
        """
        if not matches:
            return 0 # Если совпадений нет, возвращаем 0 очков

        score = 0
        for r, c in matches:
            self.board[r][c] = 0 # Устанавливаем элемент в 0 (пустое)
            score += 1 # Увеличиваем счёт за каждый удалённый элемент
        return score

    def drop_elements(self):
        """
        Опускает элементы, чтобы заполнить пустые места (0),
        и генерирует новые случайные элементы в верхней части столбцов.
        """
        for c in range(self.cols): # Проходим по каждому столбцу
            write_row = self.rows - 1 # Индекс строки, куда будем записывать НЕпустые элементы (начинаем снизу)
            for read_row in range(self.rows - 1, -1, -1): # Читаем с последней строки вверх
                if self.board[read_row][c] != 0: # Если текущий элемент НЕ пустой (не 0)
                    self.board[write_row][c] = self.board[read_row][c] # Перемещаем его вниз
                    if write_row != read_row: # Если элемент был перемещен, а не остался на месте
                        self.board[read_row][c] = 0 # Очищаем старое место элемента
                    write_row -= 1 # Переходим к следующей строке для записи
            # После перемещения существующих элементов, заполняем оставшиеся верхние строки
            # новыми случайными элементами
            for r in range(write_row + 1):
                self.board[r][c] = random.randint(1, self.num_types)


# --- Класс GameScreen: Экран игровой доски и логика UI ---
class GameScreen(Screen):
    # Kivy Properties для динамического обновления UI
    rows = NumericProperty(0)
    cols = NumericProperty(0)
    num_types = NumericProperty(5) # Количество типов элементов для игры
    
    score = NumericProperty(0)
    moves_left = NumericProperty(0)
    target_score = NumericProperty(0)

    selected_coords = ListProperty([]) # Хранит координаты (r, c) выбранной клетки
    game_board = None # Ссылка на экземпляр GameBoard
    
    animation_in_progress = False # Флаг, блокирующий ввод во время анимаций

    def on_enter(self, *args):
        """
        Вызывается каждый раз, когда этот экран становится активным.
        Инициализирует игровую сессию.
        """
        # Устанавливаем параметры игры (ходы, целевой счёт) в зависимости от выбранного размера поля
        if self.rows == 6: # Легкий (6x6)
            self.moves_left = 20
            self.target_score = 100
        elif self.rows == 8: # Средний (8x8)
            self.moves_left = 25
            self.target_score = 200
        else: # Сложный (10x10)
            self.moves_left = 30
            self.target_score = 350

        self.score = 0
        self.selected_coords = []
        # Создаем новую игровую доску для каждой сессии
        self.game_board = GameBoard(self.rows, self.cols, self.num_types)
        
        self._update_hud() # Обновляем информацию о счете и ходах в UI

        # Обязательная очистка GridLayout перед новой отрисовкой.
        # Это предотвращает наслоение виджетов при повторном входе на экран.
        if self.ids.board_layout.children:
             self.ids.board_layout.clear_widgets()
        
        # Планируем отрисовку доски на следующий кадр.
        # Это даёт Kivy время на обновление свойств GridLayout (rows/cols) из KV-файла.
        Clock.schedule_once(self._draw_board, 0)
        self.animation_in_progress = False # Сбрасываем флаг, чтобы можно было начинать игру

    def on_leave(self, *args):
        """
        Вызывается каждый раз, когда этот экран покидает видимость.
        Проводит принудительную очистку GridLayout.
        """
        # Принудительно очищаем виджеты при выходе с экрана.
        # Это критично для избежания "слишком много детей" ошибки при возвращении
        # на экран с другой сложностью/размером.
        if self.ids.board_layout.children:
            self.ids.board_layout.clear_widgets()

    def _update_hud(self):
        """Обновляет текст в метке, отображающей текущий счёт и оставшиеся ходы."""
        self.ids.score_label.text = (
            f"Счет: {self.score} / {self.target_score}\n"
            f"Ходов: {self.moves_left}"
        )

    def _draw_board(self, *args):
        """
        Отрисовывает игровое поле, создавая кнопки для каждого элемента
        на основе текущего состояния self.game_board.board.
        """
        # Перед отрисовкой убеждаемся, что сетка абсолютно пуста.
        if self.ids.board_layout.children:
            self.ids.board_layout.clear_widgets()

        self.ids.board_layout.cols = self.cols
        self.ids.board_layout.rows = self.rows

        if self.game_board:
            spacing_x = self.ids.board_layout.spacing[0] if len(self.ids.board_layout.spacing) > 0 else 0
            spacing_y = self.ids.board_layout.spacing[1] if len(self.ids.board_layout.spacing) > 1 else 0

            button_width = (self.ids.board_layout.width - (self.cols - 1) * spacing_x) / self.cols
            button_height = (self.ids.board_layout.height - (self.rows - 1) * spacing_y) / self.rows
            
            button_width = max(0, button_width)
            button_height = max(0, button_height)

            for r in range(self.rows):
                for c in range(self.cols):
                    element_value = self.game_board.board[r][c]
                    button = Button(
                        text=str(element_value),
                        font_size='32sp',
                        background_color=self._get_element_color(element_value),
                        size_hint=(None, None),
                        size=(button_width, button_height),
                        pos=(self.ids.board_layout.x + c * (button_width + spacing_x),
                             self.ids.board_layout.y + (self.rows - 1 - r) * (button_height + spacing_y))
                    )
                    button.coords = (r, c)
                    button.bind(on_release=self.on_element_press)
                    self.ids.board_layout.add_widget(button)

    def _get_element_color(self, element_value):
        """Возвращает RGB-цвет для заданного значения элемента."""
        colors = {
            1: (1, 0, 0, 1),    # Красный
            2: (0, 1, 0, 1),    # Зеленый
            3: (0, 0, 1, 1),    # Синий
            4: (1, 1, 0, 1),    # Желтый
            5: (1, 0, 1, 1),    # Пурпурный
            0: (0.5, 0.5, 0.5, 1) # Серый для пустых/удаленных элементов
        }
        return colors.get(element_value, (0.7, 0.7, 0.7, 1)) # Цвет по умолчанию

    def on_element_press(self, instance):
        """
        Обработчик нажатия на кнопку элемента.
        Управляет выбором элементов и инициирует их обмен.
        """
        # Блокируем ввод, если ходы закончились или анимация в процессе
        if self.moves_left <= 0 or self.animation_in_progress:
            return

        r, c = instance.coords # Получаем координаты нажатой кнопки

        if not self.selected_coords:
            # Если это первый выбранный элемент
            self.selected_coords = [r, c] # Сохраняем его координаты
            instance.background_color = (0.2, 0.8, 0.8, 1) # Подсвечиваем
        else:
            # Если это второй выбранный элемент, пытаемся произвести обмен
            r1, c1 = self.selected_coords[0], self.selected_coords[1]
            r2, c2 = r, c

            # Находим объекты виджетов для обмена
            widget1 = None
            widget2 = None
            for widget in self.ids.board_layout.children:
                if hasattr(widget, 'coords'):
                    if widget.coords == (r1, c1):
                        widget1 = widget
                    elif widget.coords == (r2, c2):
                        widget2 = widget
            
            # Сбрасываем подсветку первого элемента, если он был найден
            if widget1:
                original_value = self.game_board.board[r1][c1]
                widget1.background_color = self._get_element_color(original_value)

            # Пробуем поменять элементы местами в логической модели
            if self.game_board.swap_elements(r1, c1, r2, c2):
                self.animation_in_progress = True # Устанавливаем флаг, блокирующий ввод

                anim_duration = 0.3 # Длительность анимации обмена (увеличено)
                
                # Пересчитываем spacing и размеры кнопок для точного позиционирования в анимации
                spacing_x = self.ids.board_layout.spacing[0] if len(self.ids.board_layout.spacing) > 0 else 0
                spacing_y = self.ids.board_layout.spacing[1] if len(self.ids.board_layout.spacing) > 1 else 0
                button_width = widget1.width # Используем текущий размер кнопки
                button_height = widget1.height # Используем текущий размер кнопки

                # Вычисляем целевые позиции для анимации обмена
                target_pos1 = (
                    self.ids.board_layout.x + c2 * (button_width + spacing_x),
                    self.ids.board_layout.y + (self.rows - 1 - r2) * (button_height + spacing_y)
                )
                target_pos2 = (
                    self.ids.board_layout.x + c1 * (button_width + spacing_x),
                    self.ids.board_layout.y + (self.rows - 1 - r1) * (button_height + spacing_y)
                )

                # Создаём объекты анимации для каждого виджета
                anim1 = Animation(pos=target_pos1, duration=anim_duration)
                anim2 = Animation(pos=target_pos2, duration=anim_duration)

                # Запускаем анимации параллельно
                anim1.start(widget1)
                anim2.start(widget2)

                # Колбэк, который будет вызван после завершения анимации обмена
                def on_anim_complete(animation, widget):
                    animation.unbind(on_complete=on_anim_complete) 
                    
                    matches_found = self.game_board.find_matches() # Ищем совпадения после обмена
                    if matches_found:
                        self.moves_left -= 1 # Уменьшаем ходы только при успешном совпадении
                        self._update_hud() # Обновляем UI
                        self.process_matches(matches_found) # Запускаем обработку совпадений
                    else:
                        # Если совпадений нет, откатываем обмен (возвращаем элементы обратно)
                        self.game_board.swap_elements(r1, c1, r2, c2) # Откатываем в логике

                        # Создаём анимации для возврата элементов на исходные позиции
                        anim_back1 = Animation(pos=target_pos2, duration=anim_duration)
                        anim_back2 = Animation(pos=target_pos1, duration=anim_duration)

                        # Колбэк после завершения обратной анимации
                        def on_back_anim_complete(animation, widget):
                            animation.unbind(on_complete=on_back_anim_complete)
                            self._draw_board() # Перерисовываем доску, чтобы всё было на своих местах
                            self.animation_in_progress = False # Сбрасываем флаг, игра готова к новому ходу
                            self._check_game_over() # Проверяем условия окончания игры
                        
                        anim_back1.bind(on_complete=on_back_anim_complete)
                        anim_back2.bind(on_complete=on_back_anim_complete)

                        anim_back1.start(widget1)
                        anim_back2.start(widget2)
                        
                # Привязываем on_anim_complete к завершению одной из анимаций обмена
                # (достаточно одной, так как они запускаются параллельно)
                anim1.bind(on_complete=on_anim_complete) 
                
            else:
                # Если обмен невозможен (не соседние элементы), просто сбрасываем флаг
                self.animation_in_progress = False 
                self._check_game_over() # Проверяем условия игры (на всякий случай)
            
            self.selected_coords = [] # Сбрасываем выбранные координаты

    def process_matches(self, matches):
        """
        Обрабатывает найденные совпадения: удаляет их из логики, начисляет очки,
        затем инициирует визуальное исчезновение и последующее заполнение.
        """
        score_gained = self.game_board.remove_matches(matches) # Удаляем совпадения из логики
        self.score += score_gained # Добавляем очки
        self._update_hud() # Обновляем UI

        anim_duration = 0.4 # Длительность анимации исчезновения (увеличено)
        widgets_to_animate = []
        # Собираем список виджетов (кнопок), соответствующих найденным совпадениям
        for r, c in matches:
            for widget in self.ids.board_layout.children:
                if hasattr(widget, 'coords') and widget.coords == (r, c):
                    widgets_to_animate.append(widget)
                    break # Нашли виджет, переходим к следующему совпадению
        
        if not widgets_to_animate:
            self.animation_in_progress = False # Важно сбросить, если анимации не будет
            Clock.schedule_once(self._drop_and_refill, 0.1) # Сразу запускаем заполнение
            return

        completed_animations_count = 0 # Счётчик завершённых анимаций исчезновения

        # Колбэк, вызываемый после завершения КАЖДОЙ анимации исчезновения
        def on_fade_complete(animation, widget):
            nonlocal completed_animations_count

            completed_animations_count += 1
            if widget.parent:
                widget.parent.remove_widget(widget)
            
            # Если ВСЕ анимации исчезновения завершены
            if completed_animations_count == len(widgets_to_animate):
                Clock.schedule_once(self._drop_and_refill, 0.1) 
            
        for widget in widgets_to_animate:
            # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Создаём НОВЫЙ объект Animation для КАЖДОГО виджета
            current_widget_animation = Animation(
                opacity=0,
                size=(1, 1),
                duration=anim_duration
            )
            
            # Сбрасываем свойства, чтобы анимация начиналась с корректных значений
            widget.opacity = 1 
            widget.size = (widget.width, widget.height) 
            
            current_widget_animation.bind(on_complete=on_fade_complete)
            current_widget_animation.start(widget)

    def _drop_and_refill(self, dt):
        """
        Вызывается после исчезновения элементов: опускает существующие элементы,
        генерирует новые и затем проверяет на цепные реакции.
        """
        self.game_board.drop_elements() # Логика падения и заполнения

        self._draw_board() # Перерисовываем доску, чтобы отобразить новые/перемещенные элементы

        new_matches = self.game_board.find_matches() # Ищем новые совпадения (для цепных реакций)
        if new_matches:
            self.process_matches(new_matches)
        else:
            self.animation_in_progress = False 
            self._check_game_over()

    def _check_game_over(self):
        """Проверяет условия окончания игры (победа или поражение)."""
        game_over_screen = self.manager.get_screen('game_over')

        if self.score >= self.target_score:
            name_input_screen = self.manager.get_screen('name_input')
            name_input_screen.last_score = self.score # Передаём финальный счёт
            self.manager.current = 'name_input' # Переходим на экран ввода имени
        elif self.moves_left <= 0:
            game_over_screen.win_status = "Поражение"
            game_over_screen.message = f"Ходы закончились. Ваш счет: {self.score}"
            self.manager.current = 'game_over' # Переходим на экран окончания игры


# --- Класс MainMenuScreen: Главное меню игры ---
class MainMenuScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)

    def start_game(self, rows, cols):
        """Начинает новую игру с выбранными параметрами сложности."""
        game_screen = self.manager.get_screen('game')
        game_screen.rows = rows
        game_screen.cols = cols
        self.manager.current = 'game' # Переключаемся на игровой экран

    def show_highscores(self):
        """Переключается на экран таблицы рекордов."""
        highscore_screen = self.manager.get_screen('highscores')
        highscore_screen.load_highscores() # Обновляем рекорды перед показом
        self.manager.current = 'highscores' # Переключаемся на экран рекордов

    def show_how_to_play(self):
        """Переключается на экран с инструкциями по игре."""
        self.manager.current = 'how_to_play'


# --- Класс HowToPlayScreen: Экран с инструкциями ---
class HowToPlayScreen(Screen):
    def __init__(self, **kw):
        super().__init__(**kw)
        # Отложенное создание макета, чтобы window.width был доступен
        Clock.schedule_once(self._build_layout, 0)

    def _build_layout(self, dt):
        main_layout = BoxLayout(orientation='vertical', padding=10, spacing=10)

        # Заголовок
        main_layout.add_widget(Label(
            text='Как играть в "Три в ряд"',
            font_size='36sp',
            size_hint_y=None,
            height=60
        ))

        # ScrollView для прокрутки текста
        scroll_view = ScrollView(size_hint=(1, 1))
        
        instructions_text = """
        Добро пожаловать в игру "Три в ряд"!
        
        Цель игры:
        Набрать определенное количество очков за ограниченное число ходов.

        Как играть:
        1. Нажмите на любой элемент на игровом поле, чтобы выбрать его.
        2. Затем нажмите на соседний элемент (по горизонтали или вертикали), с которым хотите поменять местами выбранный элемент.
        3. Если в результате обмена образуется линия из трех или более одинаковых элементов (по горизонтали или вертикали), они исчезнут, и вы получите очки.
        4. После исчезновения элементов, новые элементы упадут сверху, чтобы заполнить пустые места. Это может вызвать цепную реакцию и новые совпадения!
        5. Продолжайте делать ходы, пока не наберете целевое количество очков или не закончатся ходы.

        Начисление очков:
        Чем больше элементов исчезает за один ход, тем больше очков вы получаете.

        Условия победы/поражения:
        * Победа: Наберите целевое количество очков (отображается вверху экрана) до того, как закончатся ходы.
        * Поражение: Ходы закончились, а вы не набрали целевое количество очков.

        Удачи в игре!
        """
        
        content_label = Label(
            text=instructions_text,
            font_size='20sp',
            size_hint_y=None, 
            # text_size теперь привязан к ширине scroll_view минус отступы
            halign='left', # Изменено на 'left' для лучшего чтения длинного текста
            valign='top'
        )
        # Привязка ширины text_size Label к ширине scroll_view с учетом padding BoxLayout
        # Используем scroll_view.width для привязки, чтобы текст растягивался на всю доступную ширину прокручиваемой области.
        # Вычитаем padding из main_layout, чтобы текст не прилипал к краям.
        content_label.bind(
            width=lambda instance, value: setattr(instance, 'text_size', (value - (main_layout.padding[0] * 2), None)),
            texture_size=lambda instance, value: setattr(instance, 'height', value[1])
        )
        # Устанавливаем ширину content_label равной ширине scroll_view, чтобы binding работал корректно
        # Это нужно, чтобы Label изначально имел правильную ширину для расчета text_size.
        scroll_view.bind(width=lambda instance, value: setattr(content_label, 'width', value))


        scroll_view.add_widget(content_label)
        main_layout.add_widget(scroll_view)

        # Кнопка "Назад"
        back_button = Button(
            text="Назад в меню",
            size_hint_y=None,
            height=50,
            on_release=self.go_back_to_menu
        )
        main_layout.add_widget(back_button)

        self.add_widget(main_layout)


    def go_back_to_menu(self, instance):
        self.manager.current = 'menu'


# --- Класс GameOverScreen: Экран окончания игры (победа/поражение) ---
class GameOverScreen(Screen):
    win_status = StringProperty("") # "Победа!" или "Поражение"
    message = StringProperty("")    # Дополнительное сообщение

    def __init__(self, **kw):
        super().__init__(**kw)
        
    def on_enter(self, *args):
        """Обновляет текст меток на экране при каждом входе."""
        self.ids.status_label.text = self.win_status
        self.ids.message_label.text = self.message


# --- Класс NameInputScreen: Экран ввода имени для рекорда ---
class NameInputScreen(Screen):
    last_score = NumericProperty(0) # Свойство для хранения последнего набранного счета

    def __init__(self, **kw):
        super().__init__(**kw)

    def on_enter(self, *args):
        """Обновляет сообщение и очищает поле ввода при входе на экран."""
        self.ids.score_display_label.text = f"Поздравляем! Ваш счет: {self.last_score}\nВведите ваше имя для таблицы рекордов:"
        self.ids.name_input_field.text = "" # Очищаем поле ввода имени

    def save_score(self, player_name):
        """Сохраняет счёт игрока в таблицу рекордов."""
        if not player_name.strip(): # Если имя пустое или состоит из пробелов
            player_name = "Аноним" # Используем имя по умолчанию
        
        score_data = {
            "name": player_name,
            "score": self.last_score
        }
        
        app = App.get_running_app() # Получаем ссылку на основной объект приложения
        app.add_highscore(score_data) # Делегируем добавление рекорда методу App
        
        # Переходим на экран таблицы рекордов
        highscore_screen = self.manager.get_screen('highscores')
        highscore_screen.load_highscores() # Обновляем список рекордов на экране
        self.manager.current = 'highscores'


# --- Класс HighscoreScreen: Экран таблицы рекордов ---
class HighscoreScreen(Screen):
    highscore_text = StringProperty("Загрузка рекордов...") # Текст для отображения рекордов

    HIGHSCORE_FILE = "highscores.json" # Имя файла для сохранения/загрузки рекордов

    def __init__(self, **kw):
        super().__init__(**kw)

    def on_enter(self, *args):
        """Загружает рекорды каждый раз при входе на экран."""
        self.load_highscores()

    def load_highscores(self):
        """Загружает рекорды из файла (JSON) и обновляет отображаемый текст."""
        # Получаем путь к директорию для пользовательских данных приложения
        self.data_dir = App.get_running_app().user_data_dir
        self.file_path = os.path.join(self.data_dir, self.HIGHSCORE_FILE)
        
        scores = []
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f: # Указываем кодировку UTF-8
                try:
                    scores = json.load(f) # Пытаемся загрузить данные
                except json.JSONDecodeError:
                    scores = [] # Если ошибка, начинаем с пустого списка
        
        scores.sort(key=lambda x: x['score'], reverse=True) # Сортируем по очкам (от большего к меньшему)
        
        if not scores:
            self.highscore_text = "Пока нет рекордов."
        else:
            formatted_scores = ["Таблица рекордов:"]
            for i, entry in enumerate(scores[:10]): # Отображаем только топ-10
                formatted_scores.append(f"{i+1}. {entry['name']}: {entry['score']} очков")
            self.highscore_text = "\n".join(formatted_scores)

    def add_highscore(self, new_score_data):
        """Добавляет новый рекорд в файл и перезагружает список рекордов."""
        self.data_dir = App.get_running_app().user_data_dir
        self.file_path = os.path.join(self.data_dir, self.HIGHSCORE_FILE)

        scores = []
        if os.path.exists(self.file_path):
            with open(self.file_path, 'r', encoding='utf-8') as f:
                try:
                    scores = json.load(f)
                except json.JSONDecodeError:
                    scores = []
        
        scores.append(new_score_data) # Добавляем новый рекорд
        
        with open(self.file_path, 'w', encoding='utf-8') as f:
            json.dump(scores, f, indent=4, ensure_ascii=False) # Сохраняем с отступами и поддержкой кириллицы
        
        self.load_highscores() # Перезагружаем, чтобы UI обновился


# --- Основной класс приложения Kivy ---
class Match3GameApp(App):
    def build(self):
        # Создаём ScreenManager для управления переходами между экранами
        sm = ScreenManager(transition=FadeTransition()) # Плавный переход между экранами

        # Добавляем все экраны в ScreenManager
        sm.add_widget(MainMenuScreen(name='menu'))
        sm.add_widget(GameScreen(name='game'))
        sm.add_widget(GameOverScreen(name='game_over'))
        sm.add_widget(NameInputScreen(name='name_input'))
        sm.add_widget(HighscoreScreen(name='highscores'))
        sm.add_widget(HowToPlayScreen(name='how_to_play')) # Добавляем новый экран инструкций
        
        return sm # Возвращаем ScreenManager как корневой виджет приложения

    def add_highscore(self, score_data):
        """
        Вспомогательный метод для добавления рекорда, доступный из любого места приложения
        через `App.get_running_app().add_highscore(...)`.
        """
        # Получаем ссылку на экран рекордов и вызываем его метод добавления
        highscore_screen = self.root.get_screen('highscores')
        highscore_screen.add_highscore(score_data)


if __name__ == "__main__":
    Match3GameApp().run()