import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:loop_mobile/api.dart';
import 'package:loop_mobile/models.dart';

Future<HttpServer> serve(Future<void> Function(HttpRequest) handler) async {
  final server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
  server.listen(handler);
  return server;
}

Future<void> reply(HttpRequest request, int status, Object body) async {
  request.response.statusCode = status;
  request.response.headers.contentType = ContentType.json;
  request.response.write(jsonEncode(body));
  await request.response.close();
}

void main() {
  group('endpoint', () {
    test('accepts private and loopback literals only', () async {
      expect(await validateLocalHost('127.0.0.1'), '127.0.0.1');
      expect(await validateLocalHost('192.168.1.4'), '192.168.1.4');
      expect(await validateLocalHost('10.0.0.2'), '10.0.0.2');
      expect(await validateLocalHost('100.83.10.68'), '100.83.10.68');
      expect(await validateLocalHost('::1'), '::1');
      expect(await validateLocalHost('fd00::1'), 'fd00::1');
      for (final bad in [
        '8.8.8.8',
        '0.0.0.0',
        '100.128.0.1',
        '100.63.255.255',
        '2001:db8::1',
        'example.com',
      ]) {
        await expectLater(
          validateLocalHost(bad),
          throwsA(isA<LoopApiException>()),
        );
      }
    });

    test('classifies address ranges', () {
      expect(isLocalAddress(InternetAddress('172.16.0.1')), isTrue);
      expect(isLocalAddress(InternetAddress('172.32.0.1')), isFalse);
      expect(isLocalAddress(InternetAddress('169.254.1.1')), isTrue);
      expect(isLocalAddress(InternetAddress('100.64.0.1')), isTrue);
      expect(isLocalAddress(InternetAddress('100.127.255.254')), isTrue);
      expect(isLocalAddress(InternetAddress('100.128.0.1')), isFalse);
      expect(isLocalAddress(InternetAddress('fe80::1')), isTrue);
      expect(isLocalAddress(InternetAddress('2606:4700::1')), isFalse);
    });
  });

  group('http protocol', () {
    late HttpServer server;
    late HttpLoopApi api;
    final requests = <String>[];

    setUp(() async {
      requests.clear();
      server = await serve((request) async {
        requests.add('${request.method} ${request.uri.path}');
        if (request.headers.value(HttpHeaders.authorizationHeader) !=
            'Bearer t0ken') {
          await reply(request, 401, {'ok': false, 'text': 'unauthorized'});
          return;
        }
        switch (request.uri.path) {
          case '/v1/snapshot':
            await reply(request, 200, {
              'daemon': {'state': 'running'},
              'current': {
                'id': 'run-1',
                'task': 'live',
                'state': 'running',
                'turns': 2,
              },
              'queue': [
                {'id': 'q000001', 'text': 'waiting', 'state': 'queued'},
              ],
              'done': [
                {
                  'id': 'run-2',
                  'task': 'done',
                  'state': 'complete',
                  'turns': 1,
                  'cost': 0.1,
                },
              ],
              'costs': {'total': 0.1},
            });
          case '/v1/dirs':
            await reply(request, 200, {
              'path': null,
              'roots': [
                {'name': 'ws', 'path': '/tmp/ws'},
              ],
              'dirs': [],
            });
          case '/v1/tasks':
            if (request.headers.contentLength <= 0) {
              await reply(request, 400, {
                'ok': false,
                'text': 'content length required',
              });
              return;
            }
            final body = jsonDecode(await utf8.decoder.bind(request).join());
            await reply(request, 200, {
              'k': 'queued',
              'item': {
                'id': 'q000002',
                'task': body['task'],
                'root': body['root'],
              },
            });
          case '/v1/runs/run-1':
            await reply(request, 200, {
              'id': 'run-1',
              'state': 'complete',
              'turns': 1,
              'terminal': true,
              'entries': [
                {
                  'kind': 'call',
                  'turn': 1,
                  'name': 'exec',
                  'args': '["ls"]',
                  'obs': 'ok',
                },
                {'kind': 'result', 'result': 'all good', 'finish': 'done'},
              ],
            });
          default:
            await reply(request, 404, {'ok': false, 'text': 'missing'});
        }
      });
      api = HttpLoopApi(
        ConnectionSettings(
          host: '127.0.0.1',
          port: server.port,
          token: 't0ken',
        ),
      );
    });

    tearDown(() async {
      api.close();
      await server.close(force: true);
    });

    test('parses snapshot, dirs, queue and logs', () async {
      final snapshot = Snapshot.fromJson(await api.snapshot());
      expect(snapshot.online, isTrue);
      expect(snapshot.current!.task, 'live');
      expect(snapshot.queue.single.task, 'waiting');
      expect(snapshot.done.single.state, 'complete');

      final listing = DirListing.fromJson(await api.dirs());
      expect(listing.roots.single.path, '/tmp/ws');

      final queued = await api.enqueue('do it', '/tmp/ws');
      expect(queued['item']['task'], 'do it');

      final log = RunLog.fromJson(await api.runLog('run-1'));
      expect(log.terminal, isTrue);
      expect(log.summary!.result, 'all good');
      expect(requests, contains('GET /v1/snapshot'));
    });

    test('maps auth and http errors', () async {
      final unauthorized = HttpLoopApi(
        ConnectionSettings(host: '127.0.0.1', port: server.port, token: 'bad'),
      );
      await expectLater(
        unauthorized.snapshot(),
        throwsA(
          isA<LoopApiException>().having(
            (e) => e.kind,
            'kind',
            ApiFailure.auth,
          ),
        ),
      );
      unauthorized.close();
      await expectLater(
        api.runLog('missing'),
        throwsA(
          isA<LoopApiException>().having(
            (e) => e.kind,
            'kind',
            ApiFailure.server,
          ),
        ),
      );
    });
  });
}
