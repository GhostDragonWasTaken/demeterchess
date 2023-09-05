import queue
import sys
import threading
import pygame
import chess
import chess.engine
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure
from PyQt5.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsPixmapItem, QGraphicsRectItem, QGraphicsLineItem, \
    QWidget, QVBoxLayout, QLabel, QPushButton, QComboBox
from PyQt5.QtGui import QPixmap, QColor
from PyQt5 import QtGui
from PyQt5 import QtCore
from PyQt5.QtWidgets import QApplication, QMainWindow, QListWidget


class EvaluationGraph(QWidget):
    def __init__(self):
        super().__init__()

        self.figure = Figure(figsize=(15, 4))
        self.canvas = FigureCanvas(self.figure)

        layout = QVBoxLayout()
        layout.addWidget(self.canvas)
        self.setLayout(layout)

        self.ax = self.figure.add_subplot(111)
        self.ax.set_xlabel('Move Number')
        self.ax.set_ylabel('Centipawns')
        self.ax.set_title('Board Evaluation')
        self.move_numbers = []
        self.scores = []

    def update_graph(self, move_number, score):
        self.move_numbers.append(move_number)
        self.scores.append(score)

        if len(self.move_numbers) >= 2:
            smoothed_move_numbers = []
            smoothed_scores = []

            for i in range(1, len(self.move_numbers)):
                smoothed_move = (self.move_numbers[i - 1] + self.move_numbers[i]) / 2
                smoothed_score = (self.scores[i - 1] + self.scores[i]) / 2
                smoothed_move_numbers.append(smoothed_move)
                smoothed_scores.append(smoothed_score)

            self.ax.clear()
            self.ax.plot(smoothed_move_numbers, smoothed_scores, marker='o', linestyle='-', color='royalblue')
        else:
            self.ax.clear()
            self.ax.plot(self.move_numbers, self.scores, marker='o', linestyle='-', color='royalblue')

        self.ax.grid(True, linestyle='--', alpha=0.7)
        self.ax.set_xlabel('Move Number')
        self.ax.set_ylabel('Evaluation Score')
        self.canvas.draw()


def init_pygame_mixer():
    pygame.mixer.init()


class ChessGUI(QMainWindow):
    def __init__(self):
        super().__init__()

        self.engine_play_button = None
        self.piece_images = None
        self.sound_thread = None
        self.setWindowTitle("DemeterChess Version 2SR")
        self.setGeometry(100, 100, 1350, 800)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #2c3e50; /* Dark blue background */
            }
            QGraphicsView {
                border: none;
            }
            QPushButton {
                background-color: #3498db; /* Bright blue button */
                color: white;
                border: none;
                padding: 10px;
                margin: 5px;
                border-radius: 5px;
            }
            QPushButton:checked {
                background-color: #2980b9; /* Darker blue when checked */
            }
            QComboBox {
                background-color: #ffffff; /* White combo box */
                color: #333333;
                padding: 5px;
                margin: 5px;
                border: 1px solid #333333;
            }
            QLabel {
                color: #ffffff; /* White text */
                font-size: 16px;
                margin-left: 10px;
                margin-top: 10px;
            }
        """)

        self.scene = QGraphicsScene(self)
        self.view = QGraphicsView(self.scene, self)
        self.view.setGeometry(0, 0, 800, 800)

        self.board = chess.Board()
        self.square_size = 100
        self.piece_size = 90
        self.selected_square = None
        self.red_overlays = []

        self.load_piece_images()
        self.highlighted_squares = set()
        self.draw_board()
        self.sound_queue = queue.Queue()
        init_pygame_mixer()
        self.start_sound_thread()

        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        self.engine_path = "stockfish.exe"
        self.engine = chess.engine.SimpleEngine.popen_uci(self.engine_path)
        self.show_engine_suggestions = True

        self.side_panel = QWidget(self)
        self.side_panel.setGeometry(800, 0, 550, 800)
        self.side_layout = QVBoxLayout(self.side_panel)

        self.engine_color = None
        self.suggestion_label = QLabel("Engine Suggestions", self.side_panel)
        self.side_layout.addWidget(self.suggestion_label)

        self.suggestion_list = QListWidget(self.side_panel)
        self.side_layout.addWidget(self.suggestion_list)

        self.engine_color_combo = QComboBox(self)
        self.engine_color_combo.addItem("Engine Plays as White")
        self.engine_color_combo.addItem("Engine Plays as Black")
        self.engine_color_combo.activated.connect(self.update_engine_color)
        self.side_layout.addWidget(self.engine_color_combo)

        self.evaluation_graph = EvaluationGraph()
        self.side_layout.addWidget(self.evaluation_graph)

        self.init_ui()

    def init_ui(self):
        toggle_engine_suggestions_button = QPushButton("Toggle Engine Suggestions", self)
        toggle_engine_suggestions_button.setCheckable(True)
        toggle_engine_suggestions_button.setChecked(True)
        toggle_engine_suggestions_button.clicked.connect(self.toggle_engine_suggestions)
        self.side_layout.addWidget(toggle_engine_suggestions_button)

        self.engine_play_button = QPushButton("Engine Play", self)
        self.engine_play_button.setCheckable(True)
        self.engine_play_button.setChecked(False)
        self.engine_play_button.clicked.connect(self.toggle_engine_play)
        self.side_layout.addWidget(self.engine_play_button)

    def toggle_engine_play(self):
        if self.engine_play_button.isChecked():
            self.engine_color = chess.BLACK if self.engine_color_combo.currentIndex() == 1 else chess.WHITE
        else:
            self.engine_color = None

    def update_engine_color(self, index):
        if index == 0:
            self.engine_color = chess.WHITE
        else:
            self.engine_color = chess.BLACK

    def toggle_engine_suggestions(self, state):
        self.show_engine_suggestions = state
        self.clear_highlights()
        self.scene.clear()
        self.draw_board()
        self.clear_suggestions()

    def clear_suggestions(self):
        self.suggestion_list.clear()

    def update_suggestions(self):
        self.clear_suggestions()
        if self.show_engine_suggestions:
            engine_moves, engine_scores = self.get_engine_moves(num_moves=10)
            for move, score in zip(engine_moves, engine_scores):
                self.suggestion_list.addItem(f"{move} ({score})")

    def load_piece_images(self):
        self.piece_images = {
            chess.PAWN: {
                chess.WHITE: QPixmap('images/wP.png'),
                chess.BLACK: QPixmap('images/bP.png')
            },
            chess.KING: {
                chess.WHITE: QPixmap('images/wK.png'),
                chess.BLACK: QPixmap('images/bK.png')
            },
            chess.KNIGHT: {
                chess.WHITE: QPixmap('images/wN.png'),
                chess.BLACK: QPixmap('images/bN.png')
            },
            chess.QUEEN: {
                chess.WHITE: QPixmap('images/wQ.png'),
                chess.BLACK: QPixmap('images/bQ.png')
            },
            chess.ROOK: {
                chess.WHITE: QPixmap('images/wR.png'),
                chess.BLACK: QPixmap('images/bR.png')
            },
            chess.BISHOP: {
                chess.WHITE: QPixmap('images/wB.png'),
                chess.BLACK: QPixmap('images/bB.png')
            }
        }

    def start_new_game(self):
        self.board.reset()
        self.clear_highlights()
        self.scene.clear()
        self.draw_board()

    def get_engine_moves(self, num_moves=4):
        result = self.engine.analyse(self.board, chess.engine.Limit(time=0.1), multipv=num_moves)
        moves = [info.get("pv")[0] for info in result]
        scores = [info.get("score", chess.engine.Cp(0)) for info in result]
        return moves, scores

    def get_king_square(self, color):
        for square in chess.SQUARES:
            piece = self.board.piece_at(square)
            if piece and piece.piece_type == chess.KING and piece.color == color:
                return square
        return None

    def exit_engine(self):
        self.engine.quit()

    def draw_board(self):
        square_size = self.square_size

        self.scene.clear()

        for rank in range(8):
            for file in range(8):
                square_color = QColor(255, 255, 255) if (rank + file) % 2 == 0 else QColor(150, 150, 150)
                square = QGraphicsRectItem(file * square_size, rank * square_size, square_size, square_size)
                square.setBrush(square_color)
                self.scene.addItem(square)

                square_idx = chess.square(file, 7 - rank)
                piece = self.board.piece_at(square_idx)
                if piece is not None:
                    pixmap = self.piece_images[piece.piece_type][piece.color]
                    if pixmap:
                        piece_item = QGraphicsPixmapItem(pixmap)
                        piece_item.setPos(file * square_size + (square_size - self.piece_size) / 2,
                                          rank * square_size + (square_size - self.piece_size) / 2)
                        scaled_pixmap = pixmap.scaled(self.piece_size, self.piece_size,
                                                      aspectRatioMode=QtCore.Qt.KeepAspectRatio)
                        piece_item.setPixmap(scaled_pixmap)
                        self.scene.addItem(piece_item)

        self.clear_red_overlays()

        white_king_square = self.get_king_square(chess.WHITE)
        black_king_square = self.get_king_square(chess.BLACK)

        if white_king_square and self.board.is_check() and self.board.king(chess.WHITE) in self.board.checkers():
            self.draw_red_overlay(white_king_square)

        if black_king_square and self.board.is_check() and self.board.king(chess.BLACK) in self.board.checkers():
            self.draw_red_overlay(black_king_square)

    def draw_red_overlay(self, square):
        file = chess.square_file(square)
        rank = 7 - chess.square_rank(square)
        red_overlay = QGraphicsRectItem(file * self.square_size, rank * self.square_size, self.square_size,
                                        self.square_size)
        red_overlay.setBrush(QColor(255, 0, 0, 50))
        self.red_overlays.append(red_overlay)
        self.scene.addItem(red_overlay)

    def clear_red_overlays(self):
        for overlay in self.red_overlays:
            self.scene.removeItem(overlay)
        self.red_overlays.clear()

    def highlight_squares(self, squares):
        for square in squares:
            file = chess.square_file(square)
            rank = 7 - chess.square_rank(square)
            highlight = QGraphicsRectItem(file * self.square_size, rank * self.square_size, self.square_size,
                                          self.square_size)
            highlight.setBrush(QColor(0, 255, 0, 100))
            self.scene.addItem(highlight)
            self.highlighted_squares.add(highlight)

    def clear_highlights(self):
        for item in self.highlighted_squares:
            self.scene.removeItem(item)
        self.highlighted_squares.clear()

    def start_sound_thread(self):
        self.sound_thread = threading.Thread(target=self.sound_player)
        self.sound_thread.daemon = True
        self.sound_thread.start()

    def sound_player(self):
        while True:
            sound_file = self.sound_queue.get()
            pygame.mixer.music.load(sound_file)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            self.sound_queue.task_done()

    def enqueue_sound(self, sound_name):
        sound_file = sound_name + '.mp3'
        self.sound_queue.put(sound_file)

    def play_sound(self, sound_name):
        self.enqueue_sound(sound_name)

    def check_sound(self):
        self.enqueue_sound("check")

    def _play_sound_thread(self, sound_file):
        self.enqueue_sound(sound_file)

    def draw_arrow(self, from_square, to_square):
        if self.show_engine_suggestions:
            from_col, from_row = chess.square_file(from_square), 7 - chess.square_rank(from_square)
            to_col, to_row = chess.square_file(to_square), 7 - chess.square_rank(to_square)

            arrow = QGraphicsLineItem(
                from_col * self.square_size + self.square_size // 2,
                from_row * self.square_size + self.square_size // 2,
                to_col * self.square_size + self.square_size // 2,
                to_row * self.square_size + self.square_size // 2
            )
            arrow.setPen(QtGui.QPen(QtCore.Qt.darkBlue, 2, QtCore.Qt.SolidLine))
            self.scene.addItem(arrow)

    def mousePressEvent(self, event):
        x = event.x() - self.view.x()
        y = event.y() - self.view.y()

        scaled_square_size = self.square_size

        file = x // scaled_square_size
        rank = y // scaled_square_size
        square = chess.square(file, 7 - rank)

        if self.engine_color and self.board.turn == self.engine_color:
            engine_moves, _ = self.get_engine_moves(num_moves=1)
            if engine_moves:
                move = engine_moves[0]
                if self.board.is_castling(move):
                    self.play_sound('castle')
                elif self.board.is_capture(move):
                    self.play_sound('capture')
                else:
                    self.play_sound('move')
                self.board.push(move)
                if self.board.is_check():
                    self.check_sound()
                self.update_suggestions()
                self.selected_square = None
                self.scene.clear()
                self.draw_board()
                return
        else:
            if self.selected_square is None:
                legal_moves = list(self.board.legal_moves)
                legal_destinations = [move.to_square for move in legal_moves if move.from_square == square]
                self.highlight_squares(legal_destinations)
                self.selected_square = square
            elif square == self.selected_square:
                self.clear_highlights()
                self.selected_square = None
            else:
                move = chess.Move(self.selected_square, square)
                if self.board.is_legal(move):
                    if self.board.is_castling(move):
                        self.play_sound('castle')
                    elif self.board.is_capture(move):
                        self.play_sound('capture')
                    else:
                        self.play_sound('move')
                    self.board.push(move)
                    self.update_suggestions()
                    if self.board.is_check():
                        self.check_sound()
                    engine_moves, engine_scores = self.get_engine_moves(num_moves=4)
                    self.clear_highlights()
                    self.scene.clear()
                    self.draw_board()
                    for move in engine_moves:
                        self.draw_arrow(move.from_square, move.to_square)

                    self.evaluation_graph.update_graph(len(self.board.move_stack), engine_scores[0].relative.score())
                self.selected_square = None
                if self.engine_color and self.board.turn == self.engine_color:
                    engine_moves, _ = self.get_engine_moves(num_moves=1)
                    if engine_moves:
                        move = engine_moves[0]
                        if self.board.is_castling(move):
                            self.play_sound('castle')
                        elif self.board.is_capture(move):
                            self.play_sound('capture')
                        else:
                            self.play_sound('move')
                        self.board.push(move)
                        if self.board.is_check():
                            self.check_sound()
                        self.update_suggestions()
                        self.selected_square = None
                        self.scene.clear()
                        self.draw_board()
                        return


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChessGUI()
    window.show()
    sys.exit(app.exec_())
