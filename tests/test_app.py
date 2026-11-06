import unittest
from app.server import response_for
from scripts.traffic import config


class AppTests(unittest.TestCase):
    def test_identifica_as_duas_versoes(self):
        for version, env in [('v1', 'blue'), ('v2', 'green')]:
            status, data = response_for('/', version, env)
            self.assertEqual(status, 200)
            self.assertEqual((data['versao'], data['ambiente']), (version, env))

    def test_regressao_afeta_somente_green(self):
        self.assertEqual(response_for('/checkout?falha=1', 'v1', 'blue')[0], 200)
        self.assertEqual(response_for('/checkout?falha=1', 'v2', 'green')[0], 500)
        self.assertEqual(response_for('/checkout', 'v2', 'green')[0], 200)
        self.assertEqual(response_for('/health', 'v2', 'green')[0], 200)

    def test_rota_inexistente(self):
        self.assertEqual(response_for('/nao-existe', 'v1', 'blue')[0], 404)

    def test_extremos_nao_deixam_servidor_de_peso_zero(self):
        self.assertNotIn('green:8000', config(0))
        self.assertNotIn('blue:8000', config(100))
        self.assertIn('green:8000 weight=10', config(10))
        self.assertIn('blue:8000 weight=90', config(10))
        for invalid in [-1, 101]:
            with self.assertRaises(ValueError):
                config(invalid)


if __name__ == '__main__':
    unittest.main()
