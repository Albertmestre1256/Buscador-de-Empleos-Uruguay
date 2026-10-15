import unittest
from unittest.mock import Mock
from resilience import generar_con_reintentos, informe_respaldo


class Fallo(Exception):
    def __init__(self, code):
        self.code = code


class RecuperacionTests(unittest.TestCase):
    def test_recupera_sobrecarga(self):
        generar = Mock(side_effect=[Fallo(503), "ofertas"])
        dormir = Mock()
        self.assertEqual(generar_con_reintentos(generar, dormir), "ofertas")
        dormir.assert_called_once_with(15)

    def test_cuota_agota_tres_intentos(self):
        generar = Mock(side_effect=Fallo(429))
        dormir = Mock()
        with self.assertRaises(Fallo):
            generar_con_reintentos(generar, dormir)
        self.assertEqual(generar.call_count, 3)
        self.assertEqual([c.args[0] for c in dormir.call_args_list], [15, 30])

    def test_no_reintenta_clave_invalida(self):
        generar = Mock(side_effect=Fallo(403))
        with self.assertRaises(Fallo):
            generar_con_reintentos(generar, Mock())
        self.assertEqual(generar.call_count, 1)

    def test_respuesta_vacia_es_fallo(self):
        with self.assertRaises(ValueError):
            generar_con_reintentos(lambda: "  ", Mock())

    def test_respaldo_conserva_evidencia(self):
        texto = "FUENTE: UTU\nURL: https://www.utu.edu.uy/\nLlamado"
        informe = informe_respaldo(texto, "HTTP 503")
        self.assertIn(texto, informe)
        self.assertIn("sin análisis de IA", informe)
        self.assertIn("HTTP 503", informe)


if __name__ == "__main__":
    unittest.main()
