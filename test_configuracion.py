import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from configuracion import cargar_perfil, cargar_sitios, construir_prompt
import main


class ConfiguracionTests(unittest.TestCase):
    def setUp(self):
        self.temporal = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporal.cleanup)
        self.archivo = Path(self.temporal.name) / "config"

    def guardar(self, contenido):
        self.archivo.write_text(contenido, encoding="utf-8")
        return self.archivo

    def test_perfil_personalizado_y_vacio(self):
        ruta = self.guardar("# Perfil\nAnalista comercial con SQL y Excel.")
        self.assertIn("SQL", cargar_perfil(ruta))
        self.guardar(" \n")
        with self.assertRaisesRegex(ValueError, "vacío"):
            cargar_perfil(ruta)

    def test_perfil_demasiado_grande(self):
        with self.assertRaisesRegex(ValueError, "12000"):
            cargar_perfil(self.guardar("a" * 12001))

    def test_sitio_desactivado_no_se_visita(self):
        datos = [{"nombre": "BPS", "url": "https://www.bps.gub.uy"},
                 {"nombre": "Pausa", "activo": False}]
        ruta = self.guardar(json.dumps(datos))
        self.assertEqual([s["nombre"] for s in cargar_sitios(ruta)], ["BPS"])

    def test_rechaza_configuraciones_invalidas(self):
        for datos in ({}, [], [{"nombre": "Local", "url": "file:///etc/passwd"}],
                      [{"nombre": "A", "url": "https://example.com", "activo": "false"}]):
            with self.subTest(datos=datos), self.assertRaises(ValueError):
                cargar_sitios(self.guardar(json.dumps(datos)))

    def test_fuentes_publicas_y_perfil_incluidos(self):
        urls = [s["url"] for s in cargar_sitios()]
        self.assertIn("https://uruguayconcursa.gub.uy/search", urls)
        for dominio in ("bps.gub.uy", "ose.com.uy", "montevideo.gub.uy", "concursos.udelar.edu.uy"):
            self.assertTrue(any(dominio in url for url in urls))
        self.assertIn("analista de", cargar_perfil())

    def test_prompt_separa_recomendaciones_y_hechos(self):
        prompt = construir_prompt("Llamado ABC https://example.com/oferta", "Analista con SQL", "2026-10-15")
        for valor in ("Llamado ABC", "https://example.com/oferta", "Analista con SQL",
                      "2026-10-15", "## Llamados encontrados", "## Recomendados para el perfil",
                      "recomendación condicionada", "No recomiendes vencidos"):
            self.assertIn(valor, prompt)


class AnalisisTests(unittest.TestCase):
    @patch.dict("os.environ", {"GEMINI_API_KEY": "clave-ficticia", "GEMINI_MODEL": "modelo-prueba"})
    @patch("main.genai.Client")
    def test_perfil_llega_a_gemini(self, cliente):
        generar = cliente.return_value.models.generate_content
        generar.return_value = Mock(text="## Recomendados para el perfil\nOferta ABC")
        resultado = main.analizar_con_ia("Oferta ABC", "Analista comercial con SQL")
        self.assertIn("Oferta ABC", resultado)
        args = generar.call_args.kwargs
        self.assertEqual(args["model"], "modelo-prueba")
        self.assertIn("Analista comercial con SQL", args["contents"])
        self.assertIn("Oferta ABC", args["contents"])

    @patch.dict("os.environ", {"GEMINI_API_KEY": "clave-ficticia"})
    @patch("main.genai.Client")
    def test_error_de_api_preserva_fuentes(self, cliente):
        cliente.return_value.models.generate_content.side_effect = main.errors.APIError(
            403, {"error": {"code": 403, "message": "No autorizado", "status": "PERMISSION_DENIED"}}
        )
        informe = main.analizar_con_ia("Fuente ABC https://example.com", "Analista")
        self.assertIn("sin análisis de IA", informe)
        self.assertIn("Fuente ABC https://example.com", informe)
        self.assertIn("403", informe)

    @patch.dict("os.environ", {"GEMINI_API_KEY": ""})
    @patch("main.genai.Client")
    def test_sin_clave_no_llama_proveedor(self, cliente):
        self.assertIn("sin análisis de IA", main.analizar_con_ia("Datos", "Perfil"))
        cliente.assert_not_called()


if __name__ == "__main__":
    unittest.main()
