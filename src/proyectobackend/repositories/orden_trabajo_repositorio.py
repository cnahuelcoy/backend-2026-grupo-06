from sqlalchemy import func, select, update

from proyectobackend.database.session import SessionLocal
from proyectobackend.domain.orden_trabajo import (
    ConflictoOrdenTrabajo, EstadoOrdenTrabajo, OrdenTrabajo,
)
from proyectobackend.models.orden_trabajo import OrdenTrabajoModel


class OrdenTrabajoRepository:
    @staticmethod
    def _to_domain(model: OrdenTrabajoModel) -> OrdenTrabajo:
        return OrdenTrabajo(
            id=model.id,
            vehiculo_id=model.vehiculo_id,
            fecha_ingreso=model.fecha_ingreso,
            descripcion_problema=model.descripcion_problema,
            kilometraje_ingreso=model.kilometraje_ingreso,
            estado=model.estado,
        )

    def crear(self, orden: OrdenTrabajo) -> OrdenTrabajo:
        with SessionLocal() as session:
            model = OrdenTrabajoModel(
                vehiculo_id=orden.vehiculo_id,
                fecha_ingreso=orden.fecha_ingreso,
                descripcion_problema=orden.descripcion_problema,
                kilometraje_ingreso=orden.kilometraje_ingreso,
                estado=orden.estado,
            )

            session.add(model)
            session.commit()
            session.refresh(model)

            orden.id = model.id
            return orden

    def listar(self) -> list[OrdenTrabajo]:
        with SessionLocal() as session:
            statement = select(OrdenTrabajoModel).order_by(
                OrdenTrabajoModel.id.asc()
            )

            modelos = session.scalars(statement).all()

            return [
                self._to_domain(model)
                for model in modelos
            ]

    def buscar_por_id(self, orden_id: int) -> OrdenTrabajo | None:
        with SessionLocal() as session:
            model = session.get(OrdenTrabajoModel, orden_id)

            if model is None:
                return None

            return self._to_domain(model)

    def listar_paginado(
        self,
        estado: EstadoOrdenTrabajo | None = None,
        ordenar_por: str = "id",
        direccion: str = "asc",
        pagina: int = 1,
        limite: int = 10,
    ) -> tuple[list[OrdenTrabajo], int]:
        columnas = {
            "id": OrdenTrabajoModel.id,
            "fecha_ingreso": OrdenTrabajoModel.fecha_ingreso,
            "kilometraje_ingreso": OrdenTrabajoModel.kilometraje_ingreso,
        }
        if ordenar_por not in columnas or direccion not in {"asc", "desc"}:
            raise ValueError("Ordenamiento de órdenes inválido")
        if pagina < 1 or not 1 <= limite <= 100:
            raise ValueError("Paginación de órdenes inválida")
        filtros = [] if estado is None else [OrdenTrabajoModel.estado == estado]
        columna = columnas[ordenar_por]
        orden = columna.desc() if direccion == "desc" else columna.asc()
        with SessionLocal() as session:
            total = session.scalar(
                select(func.count()).select_from(OrdenTrabajoModel).where(*filtros)
            )
            statement = (
                select(OrdenTrabajoModel)
                .where(*filtros)
                .order_by(orden, OrdenTrabajoModel.id.asc())
                .limit(limite)
                .offset((pagina - 1) * limite)
            )
            modelos = session.scalars(statement).all()
            return [self._to_domain(model) for model in modelos], total

    def actualizar(
        self,
        orden_id: int,
        cambios: dict,
        orden_original: OrdenTrabajo,
    ) -> OrdenTrabajo | None:
        if not cambios:
            return self.buscar_por_id(orden_id)
        campos = (
            "vehiculo_id", "fecha_ingreso", "descripcion_problema",
            "kilometraje_ingreso", "estado",
        )
        # La comparación y la escritura son una única operación SQL. Comparar
        # solamente en Python permitiría que otra transacción cambie la orden
        # entre la comprobación y el UPDATE.
        statement = (
            update(OrdenTrabajoModel)
            .where(
                OrdenTrabajoModel.id == orden_id,
                *(getattr(OrdenTrabajoModel, campo) == getattr(orden_original, campo)
                  for campo in campos),
            )
            .values(cambios)
            .returning(OrdenTrabajoModel)
        )
        with SessionLocal.begin() as session:
            model = session.scalar(statement)
            if model is not None:
                return self._to_domain(model)
            if session.get(OrdenTrabajoModel, orden_id) is None:
                return None
            raise ConflictoOrdenTrabajo()


orden_trabajo_repository_instance = OrdenTrabajoRepository()
