CREATE TABLE IF NOT EXISTS cupo_asistente (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    dia TEXT NOT NULL,
    consultas INTEGER NOT NULL CHECK (consultas > 0)
);
