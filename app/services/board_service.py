import os
import uuid

from app.core.config import get_settings
from app.models.board import Board, BoardFile
from app.repositories.board_repo import BoardRepository
from app.schemas.board import BoardCreate, BoardListItem, BoardRead, BoardUpdate


class BoardService:
    def __init__(self, repo: BoardRepository):
        self.repo = repo

    def list_boards(self, board_type: str, page: int = 1, size: int = 20) -> tuple[list[BoardListItem], int]:
        offset = (page - 1) * size
        items, total = self.repo.list_by_type(board_type, offset, size)
        return [BoardListItem.model_validate(b) for b in items], total

    def get_board(self, board_id: int) -> BoardRead:
        board = self.repo.get_by_id(board_id)
        if board is None:
            raise ValueError("게시글을 찾을 수 없습니다.")
        board.view_count += 1
        self.repo.update(board)
        return BoardRead.model_validate(board)

    def create_board(self, data: BoardCreate, author: str) -> BoardRead:
        board = Board(
            board_type=data.board_type,
            title=data.title,
            content=data.content,
            author=author,
        )
        board = self.repo.create(board)
        return BoardRead.model_validate(board)

    def update_board(self, board_id: int, data: BoardUpdate, username: str) -> BoardRead:
        board = self.repo.get_by_id(board_id)
        if board is None:
            raise ValueError("게시글을 찾을 수 없습니다.")
        if board.author != username:
            raise PermissionError("수정 권한이 없습니다.")
        if data.title is not None:
            board.title = data.title
        if data.content is not None:
            board.content = data.content
        board = self.repo.update(board)
        return BoardRead.model_validate(board)

    def delete_board(self, board_id: int, username: str, role: str) -> None:
        board = self.repo.get_by_id(board_id)
        if board is None:
            raise ValueError("게시글을 찾을 수 없습니다.")
        if board.author != username and role != "admin":
            raise PermissionError("삭제 권한이 없습니다.")
        self.repo.delete(board)

    def attach_file(self, board_id: int, filename: str, content: bytes) -> None:
        board = self.repo.get_by_id(board_id)
        if board is None:
            raise ValueError("게시글을 찾을 수 없습니다.")
        settings = get_settings()
        upload_dir = os.path.join(settings.file_upload_dir, "board")
        os.makedirs(upload_dir, exist_ok=True)
        stored = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(upload_dir, stored)
        with open(filepath, "wb") as f:
            f.write(content)
        bf = BoardFile(board_id=board_id, original_name=filename, stored_name=stored, file_size=len(content))
        self.repo.add_file(bf)
