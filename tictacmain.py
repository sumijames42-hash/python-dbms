"""
Tic-Tac-Toe Game
Python 3.x | Console-based | Two players
Run: python main.py
"""

def display_board(board):
    print()
    for r in range(3):
        print(" " + " | ".join(board[r * 3:(r + 1) * 3]))
        if r < 2:
            print("---+---+---")
    print()

def winner(board, mark):
    lines = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),
        (0, 3, 6), (1, 4, 7), (2, 5, 8),
        (0, 4, 8), (2, 4, 6)
    ]
    return any(all(board[i] == mark for i in line) for line in lines)

def play_round():
    board = [" "] * 9
    current = "X"

    while True:
        display_board(board)
        print(f"Player {'1' if current == 'X' else '2'} ({current})'s turn.")
        choice = input("Choose a cell (1-9): ").strip()

        if not choice:
            print("Input cannot be empty. Try again.")
            continue
        if not choice.isdigit():
            print("Please enter a number from 1 to 9.")
            continue

        position = int(choice)
        if position < 1 or position > 9:
            print("Number out of range. Choose 1-9.")
            continue
        if board[position - 1] != " ":
            print("That cell is already occupied. Try another.")
            continue

        board[position - 1] = current

        if winner(board, current):
            display_board(board)
            print(f"Player {'1' if current == 'X' else '2'} ({current}) wins!")
            return
        if " " not in board:
            display_board(board)
            print("The game is a draw!")
            return

        current = "O" if current == "X" else "X"

def main():
    print("=" * 32)
    print("       TIC-TAC-TOE GAME")
    print("=" * 32)
    while True:
        play_round()
        again = input("Would you like to play again? (y/n): ").strip().lower()
        if again not in ("y", "yes"):
            print("Thanks for playing. Goodbye!")
            break

if __name__ == "__main__":
    main()
