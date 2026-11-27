"""Prueba de humo de sarcae-lat.

Es el primero de los dos niveles de verificacion del dominio: el de humo, que
recorre el camino entero de punta a punta en menos de un minuto. El segundo, la
metrica minima esperada con su media y su desviacion, se anade cuando haya
modelo que medir.
"""


def test_el_paquete_se_importa():
    import src  # noqa: F401
