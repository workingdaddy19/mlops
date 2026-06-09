from sqlalchemy.orm import Session

from app.models.board import Board, BoardFile


class BoardRepository:
    def __init__(self, session: Session):
        self.session = session

    def list_by_type(self, board_type: str, offset: int = 0, limit: int = 20) -> tuple[list[Board], int]:
        query = self.session.query(Board).filter(Board.board_type == board_type)
        total = query.count()
        items = query.order_by(Board.id.desc()).offset(offset).limit(limit).all()
        return items, total

    def get_by_id(self, board_id: int) -> Board | None:
        return self.session.get(Board, board_id)

    def create(self, board: Board) -> Board:
        self.session.add(board)
        self.session.commit()
        self.session.refresh(board)
        return board

    def update(self, board: Board) -> Board:
        self.session.commit()
        self.session.refresh(board)
        return board

    def delete(self, board: Board) -> None:
        self.session.delete(board)
        self.session.commit()

    def add_file(self, board_file: BoardFile) -> BoardFile:
        self.session.add(board_file)
        self.session.commit()
        self.session.refresh(board_file)
        return board_file

    def get_file(self, file_id: int) -> BoardFile | None:
        return self.session.get(BoardFile, file_id)
