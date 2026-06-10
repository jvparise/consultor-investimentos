from sqlalchemy import select
from sqlalchemy.orm import Session

from consultor_investimentos.database.models import ImportLog


class ImportLogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def has_successful_import(self, file_hash: str) -> bool:
        """Retorna True se já existe uma importação bem-sucedida com este hash."""
        result = self._session.execute(
            select(ImportLog).where(
                ImportLog.file_hash == file_hash,
                ImportLog.status == "success",
            )
        ).scalar_one_or_none()
        return result is not None

    def create(
        self,
        file_hash: str,
        status: str,
        total_rows: int,
        valid_rows: int,
        error_rows: int,
        file_name: str | None = None,
    ) -> ImportLog:
        log = ImportLog(
            file_hash=file_hash,
            file_name=file_name,
            status=status,
            total_rows=total_rows,
            valid_rows=valid_rows,
            error_rows=error_rows,
        )
        self._session.add(log)
        self._session.flush()
        return log
