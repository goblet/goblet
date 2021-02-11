from goblet import jsonify, Response


class TestJsonify:
    headers = {'Content-Type': 'application/json'}

    def test_string(self):
        resp = jsonify('hello')
        assert resp == ('hello', 200, self.headers)

    def test_dict(self):
        resp = jsonify({'a': 'b'})
        assert resp == ('{"a":"b"}', 200, self.headers)

    def test_array(self):
        resp = jsonify([1, 2])
        assert resp == ('[1,2]', 200, self.headers)


class TestResponse:

    def test_headers(self):
        r = Response('', {'Content-Type': 'json'})
        assert r()[2] == {'Content-Type': 'json'}

    def test_status(self):
        r = Response('', status_code=401)
        assert r()[1] == 401
