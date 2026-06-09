from sqlalchemy.orm import Session

from app.models.system_settings import SystemSetting


class SettingsRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, key: str) -> SystemSetting | None:
        return self.session.get(SystemSetting, key)

    def get_value(self, key: str) -> str | None:
        row = self.session.get(SystemSetting, key)
        return row.value if row else None

    def list_all(self) -> list[SystemSetting]:
        return self.session.query(SystemSetting).order_by(SystemSetting.group, SystemSetting.key).all()

    def list_by_group(self, group: str) -> list[SystemSetting]:
        return (
            self.session.query(SystemSetting)
            .filter(SystemSetting.group == group)
            .order_by(SystemSetting.key)
            .all()
        )

    def set_value(self, key: str, value: str) -> SystemSetting:
        row = self.session.get(SystemSetting, key)
        if row is None:
            raise KeyError(f"설정 키 '{key}'가 존재하지 않습니다.")
        row.value = value
        self.session.commit()
        self.session.refresh(row)
        return row

    def upsert(self, key: str, value: str, label: str = "", group: str = "general") -> SystemSetting:
        row = self.session.get(SystemSetting, key)
        if row is None:
            row = SystemSetting(key=key, value=value, label=label, group=group)
            self.session.add(row)
        else:
            row.value = value
        self.session.commit()
        self.session.refresh(row)
        return row
