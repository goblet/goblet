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
        def start_response_headers(status, response_headers, exc_info=None):
            assert response_headers == [('Content-Type','json')] 
        r = Response('test', {'Content-Type': 'json'})
        assert r({}, start_response_headers) == ["test"]

    def test_status(self):
        def start_response_status(status, response_headers, exc_info=None):
            assert status == 401 
        r = Response('test', status_code=401)
        assert r({}, start_response_status) == ["test"]
