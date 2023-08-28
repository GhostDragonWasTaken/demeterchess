import random
import tkinter as tk
from tkinter import messagebox, simpledialog, filedialog
import chess
import chess.engine
import time
import threading
import queue
import re
import configparser
import tkinterhtml as tkhtml
from tkinterhtml import HtmlFrame
import chess.pgn
import os
from tkhtmlview import HTMLLabel

CONFIG_FILE = "config.ini"

PRODUCT_KEYS = [
    "nuh-uh"
]

class MainMenuUI(tk.Frame):
    def __init__(self, parent, chess_ui):
        super().__init__(parent)
        self.parent = parent
        self.chess_ui = chess_ui
        self.start_button = tk.Button(self, text="Start Game", command=self.start_game)
        self.start_button.pack()
        self.bot_button = tk.Button(self, text="Bot Mode - Deprecated", command=self.play_against_bot)
        self.bot_button.pack()
        self.cached_product_key = self.load_product_key()  # Load the product key from the INI file

    def start_game(self):
        if self.cached_product_key is not None:  # Check if the product key is already cached
            self.chess_ui.mode = "2-player"
            self.chess_ui.pack()
            self.pack_forget()
            return

        # Check product key before starting the game
        if self.validate_product_key():
            self.cached_product_key = self.product_key  # Cache the product key
            self.save_product_key()  # Save the product key to the INI file
            self.chess_ui.mode = "2-player"
            self.chess_ui.pack()
            self.pack_forget()

    def play_against_bot(self):
        if self.cached_product_key is not None:  # Check if the product key is already cached
            self.chess_ui.mode = "bot"
            self.chess_ui.pack()
            self.pack_forget()
            return

        # Check product key before starting the bot mode
        if self.validate_product_key():
            self.cached_product_key = self.product_key  # Cache the product key
            self.save_product_key()  # Save the product key to the INI file
            self.chess_ui.mode = "bot"
            self.chess_ui.pack()
            self.pack_forget()

    def validate_product_key(self):
        self.product_key = simpledialog.askstring("Product Key", "Enter your product key:")
        if self.product_key in PRODUCT_KEYS:
            return True
        else:
            messagebox.showerror("Invalid Product Key", "The product key is invalid. Please try again.")
            return False

    def save_product_key(self):
        config = configparser.ConfigParser()
        config.read(CONFIG_FILE)
        if not config.has_section("Product"):
            config.add_section("Product")
        config.set("Product", "Key", self.cached_product_key)
        with open(CONFIG_FILE, "w") as config_file:
            config.write(config_file)

    def load_product_key(self):
        config = configparser.ConfigParser()
        try:
            config.read(CONFIG_FILE)
            return config.get("Product", "Key")
        except (configparser.NoSectionError, configparser.NoOptionError):
            return None


class ChessUI(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.parent = parent
        self.board = chess.Board()
        self.square_size = 64
        self.canvas_width = self.square_size * 8
        self.canvas_height = self.square_size * 8

        self.parent.title("tkChessUI")

        self.title_label = tk.Label(self, text="♞ Chess ♞", font=("Arial", 16, "bold"))
        self.title_label.pack(pady=10)

        self.chessboard_frame = tk.Frame(self)
        self.chessboard_frame.pack(padx=10, pady=5, side="top")

        self.canvas = tk.Canvas(self.chessboard_frame, width=self.canvas_width, height=self.canvas_height)
        self.canvas.pack(side="left", fill="both", expand=True)

        self.captured_pieces_frame = tk.Frame(self.chessboard_frame)
        self.captured_pieces_frame.pack(side="right", fill="both", expand=True)

        self.captured_pieces_label = tk.Label(self.captured_pieces_frame, text="Captured Pieces",
                                              font=("Arial", 12, "bold"))
        self.captured_pieces_label.pack(pady=5)
        self.captured_pieces_text = ""  # Keep track of captured pieces as a string

        self.captured_pieces_text = tk.Text(self.captured_pieces_frame, width=10, height=10, font=("Arial", 12))
        self.captured_pieces_text.pack(side="top", fill="both", expand=True)

        self.mode = ""  # Game mode ("2-player" or "bot")

        self.selected_square = None
        self.last_opponent_move = None  # Track the last move made by the opponent
        self.move_history = []  # Move history list

        self.draw_board()
        self.canvas.bind("<Button-1>", self.handle_click)

        self.move_listbox = tk.Listbox(self.chessboard_frame, font=("Arial", 12))
        self.move_listbox.pack(side="bottom", fill="both", expand=True)
        self.move_listbox.bind("<<ListboxSelect>>", self.show_selected_move)  # Add selection binding

        self.analysis_text = tk.Text(self, width=25, height=10, font=("Arial", 12))
        self.analysis_text.pack(side="right", fill="both", expand=True)

        self.depth_label = tk.Label(self, text="Analysis Depth", font=("Arial", 12))
        self.depth_label.pack()
        self.analysis_depth = tk.StringVar()
        self.analysis_depth.set("10")  # Default analysis depth
        self.depth_entry = tk.Entry(self, textvariable=self.analysis_depth, font=("Arial", 12))
        self.depth_entry.pack()

        self.engine_enabled = tk.BooleanVar()
        self.engine_enabled.set(True)  # Default is enabled

        self.engine_select_label = tk.Label(self, text="Select Engine", font=("Arial", 12))
        self.engine_select_label.pack()
        self.selected_engine = tk.StringVar()
        self.selected_engine.set("komodo.exe")  # Default engine
        self.engine_select = tk.OptionMenu(self, self.selected_engine, "komodo.exe")
        self.engine_select.pack()

        self.engine_toggle_checkbox = tk.Checkbutton(self, text="Enable Engine", variable=self.engine_enabled,
                                                     command=self.toggle_engine, font=("Arial", 12))
        self.engine_toggle_checkbox.pack()

        self.reset_button = tk.Button(self, text="Restart Game", command=self.reset_board, font=("Arial", 12))
        self.reset_button.pack()

        self.engine_config_button = tk.Button(self, text="Engine Config", command=self.configure_engine, font=("Arial", 12))
        self.engine_config_button.pack()

        self.analysis_thread = None  # Thread for position analysis

        self.engine = None  # Placeholder for the chess engine
        self.engine_options = {}  # Engine configurations for each engine
        self.engine_processes = {
            "komodo.exe": "komodo.exe",
        }
        # Set the number of principal variations
        self.multipv = 3  # Number of principal variations to display

    def show_about(self):
        about_dialog = tk.Toplevel(self.parent)
        about_dialog.title("About")

        # Get the current script directory
        current_dir = os.path.dirname(os.path.realpath(__file__))

        # Read the content of the HTML file
        about_file_path = os.path.join(current_dir, "Help.html")
        with open(about_file_path, "r") as about_file:
            about_html = about_file.read()

        # Create an HTMLLabel widget to display the HTML content
        about_label = HTMLLabel(about_dialog, html=about_html)
        about_label.pack(fill="both", expand=True)

    def show_tou(self):
        about_dialog = tk.Toplevel(self.parent)
        about_dialog.title("About")

        # Get the current script directory
        current_dir = os.path.dirname(os.path.realpath(__file__))

        # Read the content of the HTML file
        about_file_path = os.path.join(current_dir, "tou.html")
        with open(about_file_path, "r") as about_file:
            about_html = about_file.read()

        # Create an HTMLLabel widget to display the HTML content
        about_label = HTMLLabel(about_dialog, html=about_html)
        about_label.pack(fill="both", expand=True)

    def create_menus(self):
        menubar = tk.Menu(self.parent)
        self.parent.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="New Game", command=self.reset_board)
        file_menu.add_command(label="Open PGN", command=self.open_pgn)

        # Options menu
        options_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Options", menu=options_menu)
        options_menu.add_command(label="Configure Engine", command=self.configure_engine)
        options_menu.add_separator()
        self.engine_enabled_var = tk.BooleanVar(value=True)
        options_menu.add_checkbutton(label="Enable Engine", variable=self.engine_enabled_var, command=self.toggle_engine)

        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self.show_about)

        tou_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Terms of Use", menu=tou_menu)
        tou_menu.add_command(label="About", command=self.show_tou)

    def open_pgn(self):
        pgn_file_path = filedialog.askopenfilename(filetypes=[("PGN Files", "*.pgn")])
        if pgn_file_path:
            try:
                with open(pgn_file_path, "r") as pgn_file:
                    game = chess.pgn.read_game(pgn_file)
                    self.board = game.board()
                    self.move_history = list(game.mainline_moves())
                    self.draw_board()
                    self.update_move_history()
                    self.show_message("PGN loaded successfully.")
            except Exception as e:
                messagebox.showerror("Error", f"Failed to open PGN: {e}")

    def toggle_engine(self):
        if self.engine_enabled.get():
            self.engine_enabled.set(True)
            self.analyze_position_with_thread()  # Resume analysis if the engine is enabled
        else:
            self.engine_enabled.set(False)
            # Stop analysis if the engine is disabled
            if self.analysis_thread is not None:
                self.analysis_thread.join()  # Wait for the analysis thread to finish

    def configure_engine(self):
        engine_path = self.selected_engine.get()
        if engine_path:
            if engine_path not in self.engine_options or self.engine_options[engine_path] is None:
                self.engine_options[engine_path] = self.fetch_engine_options(engine_path)

            options = self.engine_options[engine_path]

            if options is None:
                messagebox.showerror("Error", "Failed to fetch engine options.")
                return

            dialog = tk.Toplevel(self)
            dialog.title("Engine Configuration [Doesn't work as of 1.22.0]")

            # Create configuration widgets for each option
            skill_label = tk.Label(dialog, text="Skill")
            skill_label.pack()
            skill_scale = tk.Scale(dialog, from_=0, to=25, orient=tk.HORIZONTAL)
            skill_scale.set(options.get("Skill", 0))
            skill_scale.pack()

            # Create configuration widgets for each option
            multipv_label = tk.Label(dialog, text="MultiPV")
            multipv_label.pack()
            multipv_scale = tk.Scale(dialog, from_=0, to=5, orient=tk.HORIZONTAL)
            multipv_scale.set(self.multipv)
            multipv_scale.pack()

            threads_label = tk.Label(dialog, text="Threads")
            threads_label.pack()
            threads_entry = tk.Entry(dialog)
            threads_entry.insert(tk.END, str(options.get("Threads", 1)))
            threads_entry.pack()

            hash_label = tk.Label(dialog, text="Hash Size (MB)")
            hash_label.pack()
            hash_entry = tk.Entry(dialog)
            hash_entry.insert(tk.END, str(options.get("Hash", 16)))
            hash_entry.pack()

            # Apply and close buttons
            apply_button = tk.Button(dialog, text="Apply",
                                     command=lambda: self.apply_engine_config(dialog, threads_entry.get(),
                                                                              hash_entry.get(),
                                                                              skill_scale.get()))
            apply_button.pack()
            close_button = tk.Button(dialog, text="Close", command=dialog.destroy)
            close_button.pack()

    def fetch_engine_options(self, engine_path):
        options = {}
        engine_process = self.engine_processes[engine_path]
        engine = chess.engine.SimpleEngine.popen_uci(engine_process)
        try:
            for option_str in engine.options:
                match = re.match(r'^name\s+(\w+).*default\s+([^"]+|"[^"]+")', option_str)
                if match:
                    option_name = match.group(1)
                    option_value = match.group(2).strip('"')
                    options[option_name] = option_value
        finally:
            engine.quit()

        return options

    def apply_engine_config(self, dialog, threads, hash_size, skill):
        engine_path = self.selected_engine.get()
        if engine_path:
            confirmation = messagebox.askquestion(
                "Confirmation",
                "Are you sure you want to change the chess engine?",
                icon="warning"
            )
            if confirmation == "yes":
                if self.engine is not None:
                    self.engine.quit()  # Quit the engine if it exists

                self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)

                # Configure engine options
                options = {
                    "Threads": int(threads),
                    "Hash": int(hash_size),
                    "MultiPV": self.multipv,  # Add the MultiPV value to the options
                }
                if "Skill" in self.engine_options[engine_path]:
                    options["Skill"] = int(skill)

                self.engine.quit()  # Quit the engine if it exists

                print("Applying options:", options)  # Add this line to see the applied options
                self.engine.configure(options)

                # Reinitialize the engine with the new options
                self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)

            dialog.destroy()

    def reset_board(self):
        self.board.reset()
        self.selected_square = None
        self.move_history.clear()  # Clear move history
        self.move_listbox.delete(0, tk.END)  # Clear move history list
        self.draw_board()
        self.captured_pieces_text.delete("1.0", "end")
        self.analysis_text.delete("1.0", "end")
        self.analysis_thread = None  # Reset the analysis thread

    def draw_board(self):
        colors = ["#F0D9B5", "#B58863"]  # Light and dark square colors

        for row in range(8):
            for col in range(8):
                color_idx = (row + col) % 2
                color = colors[color_idx]
                x1 = col * self.square_size
                y1 = row * self.square_size
                x2 = x1 + self.square_size
                y2 = y1 + self.square_size
                self.canvas.create_rectangle(x1, y1, x2, y2, fill=color)

        # Draw ranks (numbers)
        for row in range(8):
            x = self.canvas_width
            y = row * self.square_size + self.square_size // 2
            self.canvas.create_text(x, y, text=str(8 - row), font=("Arial", 12), fill="black", anchor="e")

        # Draw files (letters)
        files = "abcdefgh"
        for col in range(8):
            x = col * self.square_size + self.square_size // 2
            y = self.canvas_height - self.square_size // 4
            self.canvas.create_text(x, y, text=files[col], font=("Arial", 12), fill="black", anchor="n")

        # Draw pieces
        piece_symbols = {
            chess.PAWN: "\u265F",  # ♟
            chess.KNIGHT: "\u265E",  # ♞
            chess.BISHOP: "\u265D",  # ♝
            chess.ROOK: "\u265C",  # ♜
            chess.QUEEN: "\u265B",  # ♛
            chess.KING: "\u265A",  # ♚
        }

        # Clear the captured pieces text
        self.captured_pieces_text.delete("1.0", "end")

        for row in range(8):
            for col in range(8):
                square = chess.square(col, 7 - row)
                piece = self.board.piece_at(square)
                if piece:
                    piece_symbol = piece_symbols[piece.piece_type]
                    color = "white" if piece.color == chess.WHITE else "black"
                    x = col * self.square_size
                    y = row * self.square_size
                    # Increase font size for clearer rendering
                    font_size = self.square_size - 25
                    self.canvas.create_text(x + self.square_size // 2, y + self.square_size // 2, text=piece_symbol,
                                            font=("Arial", font_size), fill=color, justify="center")
                else:
                    # If the square is empty, check if it's a captured piece
                    captured_piece = self.board.piece_at(square)
                    if captured_piece:
                        piece_symbol = piece_symbols[captured_piece.piece_type]
                        color = "white" if captured_piece.color == chess.WHITE else "black"
                        # Append the captured piece to the captured_pieces_text
                        self.captured_pieces_text.insert("end", f"{piece_symbol} ", (color,))
        self.captured_pieces_text.insert("end", "\n")  # Add a newline after each move

    def handle_click(self, event):
        col = event.x // self.square_size
        row = 7 - (event.y // self.square_size)
        square = chess.square(col, row)
        piece = self.board.piece_at(square)

        if self.mode == "2-player":
            if self.selected_square:
                moves = self.board.legal_moves
                selected_move = chess.Move(from_square=self.selected_square, to_square=square)
                if selected_move in moves:
                    if self.board.is_castling(selected_move):
                        self.board.push(selected_move)
                        self.move_history.append(selected_move)
                        self.update_move_history()
                    else:
                        self.board.push(selected_move)
                        self.move_history.append(selected_move)
                    self.selected_square = None
                    if self.board.is_checkmate():
                        self.show_message("Checkmate! You win!")
                    elif self.board.is_stalemate():
                        self.show_message("Stalemate! It's a draw!")
                else:
                    self.selected_square = square
            elif piece:
                self.selected_square = square

            self.canvas.delete("highlight")
            self.draw_board()
            self.highlight_square(self.selected_square, "yellow")
            self.highlight_legal_moves(self.selected_square, "green")
            self.analyze_position_with_thread()

            self.update_move_history()  # Update move history after each move

        elif self.mode == "bot":
            if self.board.turn == chess.WHITE:
                if self.selected_square:
                    moves = self.board.legal_moves
                    selected_move = chess.Move(from_square=self.selected_square, to_square=square)
                    if selected_move in moves:
                        if self.board.is_castling(selected_move):
                            self.board.push(selected_move)
                            self.move_history.append(selected_move)
                            self.update_move_history()
                        else:
                            self.board.push(selected_move)
                            self.move_history.append(selected_move)
                        self.selected_square = None
                        if self.board.is_checkmate():
                            self.show_message("Checkmate! You win!")
                        elif self.board.is_stalemate():
                            self.show_message("Stalemate! It's a draw!")
                    else:
                        self.selected_square = square
                elif piece:
                    self.selected_square = square

                self.canvas.delete("highlight")
                self.draw_board()
                self.highlight_square(self.selected_square, "yellow")
                self.highlight_legal_moves(self.selected_square, "green")
                self.analyze_position_with_thread()

                self.update_move_history()  # Update move history after each move

            if self.board.turn == chess.BLACK:
                self.after(500, self.make_bot_move)

            if self.last_opponent_move is None:
                return  # Return if the bot has no previous opponent move

            if self.selected_square:
                self.selected_square = None
                self.canvas.delete("highlight")
                self.draw_board()
                self.analyze_position_with_thread()
                return

            self.make_bot_move()

            self.update_move_history()  # Update move history after each move

    def make_bot_move(self):
        depth = int(self.analysis_depth.get())
        engine_path = self.selected_engine.get()

        self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)

        # Start the timer
        start_time = time.time()

        # Calculate the bot's move in a separate thread
        bot_thread = threading.Thread(target=self.calculate_bot_move, args=(depth,))
        bot_thread.start()

    def execute_bot_move(self, time_limit):
        if not self.engine_enabled.get():
            return  # Return if the engine is disabled

        if self.engine is None:
            engine_path = self.selected_engine.get()
            self.engine = chess.engine.SimpleEngine.popen_uci(engine_path)

        result_queue = queue.Queue()

        # Create a thread for the bot move
        bot_thread = threading.Thread(target=self.calculate_bot_move, args=(time_limit, result_queue))
        bot_thread.start()

        # Wait for the bot thread to finish and get the result
        bot_thread.join()

        try:
            result = result_queue.get(timeout=1)  # Timeout set to 1 second
            if result:
                move, elapsed_time = result

                # Perform the move and update the move history
                self.board.push(move)
                self.last_opponent_move = move

                self.canvas.delete("highlight")
                self.draw_board()
                self.analyze_position_with_thread()  # Start analysis in a separate thread

                if self.board.is_checkmate():
                    self.show_message("Checkmate! You lose!")
                elif self.board.is_stalemate():
                    self.show_message("Stalemate! It's a draw!")

                print("Bot's move took:", elapsed_time, "seconds")  # Optional: Print the bot's move time
        except queue.Empty:
            print("Bot move calculation timed out. Try increasing the time limit.")

    def calculate_bot_move(self, depth):
        try:
            # Search for the best move with the given depth
            result = self.engine.play(self.board, chess.engine.Limit(depth=depth))

            # Execute the bot's move on the board
            self.board.push(result.move)
            self.last_opponent_move = result.move

            # Update move history and redraw the board
            self.move_history.append(result.move)
            self.update_move_history()
            self.canvas.delete("highlight")
            self.draw_board()

            if self.board.is_checkmate():
                self.show_message("Checkmate! You lose!")
            elif self.board.is_stalemate():
                self.show_message("Stalemate! It's a draw!")

        except chess.engine.EngineTerminatedError:
            # The engine was terminated, create a new one for the next move
            self.engine = chess.engine.SimpleEngine.popen_uci(self.selected_engine.get())

    def highlight_square(self, square, color):
        if square is not None:
            row, col = 7 - chess.square_rank(square), chess.square_file(square)
            x1 = col * self.square_size
            y1 = row * self.square_size
            x2 = x1 + self.square_size
            y2 = y1 + self.square_size
            self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags="highlight")

    def highlight_legal_moves(self, square, color):
        if square is not None:
            moves = self.board.legal_moves
            for move in moves:
                if move.from_square == square:
                    row, col = 7 - chess.square_rank(move.to_square), chess.square_file(move.to_square)
                    x1 = col * self.square_size
                    y1 = row * self.square_size
                    x2 = x1 + self.square_size
                    y2 = y1 + self.square_size
                    self.canvas.create_rectangle(x1, y1, x2, y2, outline=color, width=2, tags="highlight")

    def analyze_position_thread(self):
        if not self.engine_enabled.get():
            return  # Return if the engine is disabled

        depth = self.analysis_depth.get()
        multipv = self.multipv  # Get the MultiPV value from the instance variable
        engine_path = self.selected_engine.get()
        engine = chess.engine.SimpleEngine.popen_uci(engine_path)

        # Start the analysis with the specified MultiPV
        result = engine.analyse(self.board, chess.engine.Limit(depth=int(depth)), multipv=multipv)

        self.analysis_text.delete("1.0", "end")

        for idx, info in enumerate(result):
            move = info["pv"][0]  # Get the principal variation move
            score = info.get("score")
            depth = info.get("depth")

            self.analysis_text.insert("end", f"Engine Line {idx + 1}: {move}\n")

            if score is not None:
                if score.is_mate():
                    eval_text = "Mate in " + str(score.relative.mate()) + " moves"
                else:
                    eval_text = "Evaluation: " + str(score.relative.score() / 100.0)
                self.analysis_text.insert("end", eval_text + "\n")
            else:
                self.analysis_text.insert("end", "Evaluation: N/A\n")
            self.analysis_text.insert("end", "Depth: " + str(depth) + "\n")

            if idx < 3:
                # Highlight the top 3 moves with green lines
                self.highlight_move(move)

        self.last_opponent_move = result[0]["pv"][0]  # Update last opponent move
        engine.quit()

    def highlight_move(self, move):
        from_square = move.from_square
        to_square = move.to_square
        row_from = 7 - chess.square_rank(from_square)
        col_from = chess.square_file(from_square)
        row_to = 7 - chess.square_rank(to_square)
        col_to = chess.square_file(to_square)
        x1 = col_from * self.square_size + self.square_size // 2
        y1 = row_from * self.square_size + self.square_size // 2
        x2 = col_to * self.square_size + self.square_size // 2
        y2 = row_to * self.square_size + self.square_size // 2
        self.canvas.create_line(x1, y1, x2, y2, fill="green", width=4, tags="highlight")

    def analyze_position_with_thread(self):
        if self.analysis_thread is None or not self.analysis_thread.is_alive():
            self.analysis_thread = threading.Thread(target=self.analyze_position_thread)
            self.analysis_thread.start()

    def update_move_history(self):
        self.move_listbox.delete(0, tk.END)  # Clear the move history list

        for move_number, move in enumerate(self.move_history, start=1):
            move_str = f"{move_number}. {move.uci()}"
            self.move_listbox.insert(tk.END, move_str)  # Add each move to the listbox

    def show_selected_move(self, event):
        selected_index = self.move_listbox.curselection()
        if selected_index:
            move_number = (selected_index[0] // 2) + 1
            messagebox.showinfo("Move Details", f"Move {move_number}: {self.move_listbox.get(selected_index)}")

    def show_message(self, message):
        messagebox.showinfo("Game Over", message)
        # Clear move history when the game is over
        self.move_history.clear()


if __name__ == "__main__":
    root = tk.Tk()

    # Set the icon for the application window
    icon_file_path = "logo.ico"
    try:
        root.iconbitmap(icon_file_path)
    except tk.TclError:
        pass  # If the icon cannot be loaded, simply skip setting the icon

    chess_ui = ChessUI(root)
    main_menu_ui = MainMenuUI(root, chess_ui)

    main_menu_ui.pack()
    chess_ui.create_menus()  # Call the create_menus function to add menus to the chess UI
    root.mainloop()
