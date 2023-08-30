import concurrent.futures
import chess
import numpy as np
import tensorflow as tf
import os
import time

# Load the pre-trained model
model = tf.keras.models.load_model("ARES.h5")

def board_to_features(board):
    features = np.zeros(64)
    for square in chess.SQUARES:
        piece = board.piece_at(square)
        if piece is not None:
            features[square] = piece.piece_type + (piece.color == board.turn) * 6
    return features


def evaluate_boards(boards, batch_size=32):
    def evaluate_batch(batch):
        features = np.array([board_to_features(board) for board in batch])
        stacked_features = tf.stack(features, axis=0)
        return model.predict(stacked_features, batch_size=len(stacked_features))

    num_boards = len(boards)
    batched_boards = [boards[i:i + batch_size] for i in range(0, num_boards, batch_size)]

    predictions = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        for batch_predictions in executor.map(evaluate_batch, batched_boards):
            predictions.extend(batch_predictions)

    return predictions


# Initialize a global transposition table dictionary
transposition_table = {}


def select_best_move(board, num_moves=1, batch_size=32, depth=1, num_threads=4):
    legal_moves = list(board.legal_moves)
    num_legal_moves = len(legal_moves)
    num_batches = (num_legal_moves + batch_size - 1) // batch_size
    moves_batches = [legal_moves[i:i + batch_size] for i in range(0, num_legal_moves, batch_size)]

    best_moves_scores = []

    def evaluate_moves_batch(moves_batch):
        batch_scores = []

        capturing_moves = []
        non_capturing_moves = []

        for move in moves_batch:
            # Create a new board instance for this thread
            thread_board = board.copy()
            thread_board.push(move)
            if thread_board.is_capture(move):
                capturing_moves.append(move)
            else:
                non_capturing_moves.append(move)

        capturing_scores = []
        non_capturing_scores = []

        # Evaluate capturing moves first
        for move in capturing_moves:
            thread_board = board.copy()
            thread_board.push(move)
            score = -alpha_beta_with_transposition(thread_board, depth - 1, -float('inf'), float('inf'))
            capturing_scores.append((move, score))

        non_capturing_moves.sort(key=lambda move: -evaluate_board(board, depth - 2))  # LMR reduction
        for move in non_capturing_moves:
            thread_board = board.copy()
            thread_board.push(move)
            score = -alpha_beta_with_transposition(thread_board, depth - 2, -float('inf'), float('inf'))
            non_capturing_scores.append((move, score))

        batch_scores.extend(capturing_scores)
        batch_scores.extend(non_capturing_scores)

        return batch_scores

    with concurrent.futures.ThreadPoolExecutor(max_workers=num_threads) as executor:
        for batch_scores in executor.map(evaluate_moves_batch, moves_batches):
            best_moves_scores.extend(batch_scores)

    best_moves_scores.sort(key=lambda x: x[1], reverse=True)

    selected_moves = [move for move, _ in best_moves_scores[:num_moves]]

    # Perform a more intensive evaluation for the selected move(s)
    for move in selected_moves:
        board.push(move)
        intensive_score = -alpha_beta_with_transposition(board, depth - 1, -float('inf'), float('inf'))
        board.pop()

        for i, (eval_move, score) in enumerate(best_moves_scores):
            if eval_move == move:
                best_moves_scores[i] = (eval_move, (score + intensive_score) / 2)  # Average the scores

    best_moves_scores.sort(key=lambda x: x[1], reverse=True)

    return [move for move, _ in best_moves_scores[:num_moves]]


def alpha_beta_with_transposition(board, depth, alpha, beta):
    # Check if the current position has already been evaluated
    if board.fen() in transposition_table:
        return transposition_table[board.fen()]

    if depth == 0:
        score = evaluate_board(board, 0)  # Evaluate the current position
        transposition_table[board.fen()] = score
        return score

    legal_moves = list(board.legal_moves)
    best_score = -float('inf')

    for move in legal_moves:
        board.push(move)
        score = -alpha_beta_with_transposition(board, depth - 1, -beta, -alpha)
        board.pop()

        if score >= beta:
            return beta  # Beta cut-off
        if score > best_score:
            best_score = score
            if score > alpha:
                alpha = score

    transposition_table[board.fen()] = best_score
    return best_score


def evaluate_board(board, depth):
    if depth == 0:
        return evaluate_boards([board])[0]  # Evaluate the current position
    legal_moves = list(board.legal_moves)
    best_score = -float('inf')

    for move in legal_moves:
        board.push(move)
        score = -evaluate_board(board, depth - 1)  # Negamax with alpha-beta pruning
        board.pop()

        if score > best_score:
            best_score = score

    return best_score


def play_game(num_moves=1, batch_size=32, num_threads=4):
    board = chess.Board()

    while not board.is_game_over():
        print(board)
        legal_moves = list(board.legal_moves)

        if len(legal_moves) == 0:
            print("Game over: Stalemate!")
            break

        depth = int(input("Enter the search depth for this move: "))  # Prompt for the search depth

        # Measure time before starting move evaluation
        start_time = time.time()

        best_moves = select_best_move(board, num_moves, batch_size, depth, num_threads)
        best_moves_san = [board.san(move) for move in best_moves]
        print("AI suggests top {} move(s):".format(num_moves), ", ".join(best_moves_san))
        # Measure elapsed time for move evaluation
        elapsed_time = time.time() - start_time
        print("Move evaluation time:", elapsed_time, "seconds")
        move_san = input("Enter your move (SAN notation): ")

        try:
            move = board.parse_san(move_san)
            if move in legal_moves:
                board.push(move)
            else:
                print("Invalid move!")
        except ValueError:
            print("Invalid move format!")
        os.system('cls')

    print("Game Over")
    print("Result:", board.result())


while True:
    os.system('cls')
    print("ARES")
    num_moves = int(input("Enter the number of moves to recommend: "))
    batch_size = int(input("Enter the batch size for evaluation (e.g., 32): "))
    num_threads = int(input("Enter the number of threads: "))
    play_game(num_moves, batch_size, num_threads)
    play_again = input("Do you want to play again? (yes/no): ")
    if play_again.lower() != "yes":
        break
