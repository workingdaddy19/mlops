from sqlalchemy.orm import Session

from app.models.user import User


class UserRepository:
    def __init__(self, session: Session):
        self.session = session

    def get_by_username(self, username: str) -> User | None:
        return self.session.query(User).filter(User.username == username).first()

    def get_by_id(self, user_id: int) -> User | None:
        return self.session.get(User, user_id)

    def list_all(self) -> list[User]:
        return self.session.query(User).order_by(User.id).all()

    def create(self, user: User) -> User:
        self.session.add(user)
        self.session.commit()
        self.session.refresh(user)
        return user
