import 'package:flutter_test/flutter_test.dart';
import 'package:loop_mobile/api.dart';
import 'package:loop_mobile/models.dart';
import 'package:loop_mobile/store.dart';

import 'fake_api.dart';

void main() {
  test('saved settings are available before an auto-connect', () {
    const saved =
        ConnectionSettings(host: '127.0.0.1', port: 8787, token: 't0ken');
    final store = LoopStore(apiFactory: (_) => FakeApi(), saved: saved);
    addTearDown(store.dispose);
    expect(store.settings, saved);
    expect(store.connected, isFalse);
  });

  test('connect derives roots and selected workspace from the server', () async {
    final api = FakeApi();
    final store = LoopStore(apiFactory: (_) => api, pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    expect(await store.connect('127.0.0.1', 8787, 'token'), isTrue);
    expect(store.connected, isTrue);
    expect(store.online, isTrue);
    expect(store.listing.roots.single.path, '/tmp/ws');
    expect(store.selectedRoot, '/tmp/ws');
    expect(store.snapshot.daemonState, 'running');
    expect(api.snapshots, 1);
  });

  test('submit uses the selected root and refreshes the snapshot', () async {
    final api = FakeApi();
    final store = LoopStore(apiFactory: (_) => api, pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    await store.connect('127.0.0.1', 8787, 'token');
    store.selectRoot('/tmp/ws/src');
    final ok = await store.submitTask('  do the thing  ');
    expect(ok, isTrue);
    expect(api.enqueuedTask, 'do the thing');
    expect(api.enqueuedRoot, '/tmp/ws/src');
  });

  test('watchRun loads a run log and refreshActiveRun picks up new entries', () async {
    final api = FakeApi();
    final store = LoopStore(apiFactory: (_) => api, pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    await store.connect('127.0.0.1', 8787, 'token');
    await store.watchRun('run-1');
    expect(store.activeRunId, 'run-1');
    expect(store.runLog!.callCount, 1);
    expect(api.logs, 1);
    api.logData = {
      'id': 'run-1',
      'state': 'complete',
      'turns': 1,
      'terminal': true,
      'entries': [
        {'kind': 'call', 'turn': 1, 'name': 'exec', 'args': '[]', 'obs': 'ok'},
        {'kind': 'result', 'result': 'finished', 'finish': 'done'}
      ],
    };
    await store.refreshActiveRun();
    expect(store.runLog!.terminal, isTrue);
    expect(store.runLog!.summary!.result, 'finished');
    expect(api.logs, 2);
    store.unwatchRun('run-1');
    expect(store.activeRunId, isNull);
    expect(store.runLog, isNull);
  });

  test('connection and polling failures stay visible without inventing state', () async {
    final api = FakeApi()..failWith = const LoopApiException(ApiFailure.auth, 'invalid token');
    final store = LoopStore(apiFactory: (_) => api, pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    final ok = await store.connect('127.0.0.1', 8787, 'token');
    expect(ok, isFalse);
    expect(store.connected, isTrue);
    expect(store.online, isFalse);
    expect(store.error, 'invalid token');
    expect(store.snapshot.current, isNull);
  });

  test('disconnect closes the client and resets derived state', () async {
    final api = FakeApi();
    final store = LoopStore(apiFactory: (_) => api, pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    await store.connect('127.0.0.1', 8787, 'token');
    store.disconnect();
    expect(api.closed, isTrue);
    expect(store.connected, isFalse);
    expect(store.selectedRoot, isNull);
    expect(store.snapshot, Snapshot.empty);
  });

  test('a bad host is rejected before an API is created', () async {
    var created = 0;
    final store = LoopStore(
        apiFactory: (_) {
          created++;
          return FakeApi();
        },
        pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    expect(await store.connect('8.8.8.8', 8787, 'token'), isFalse);
    expect(created, 0);
    expect(store.error, contains('private or loopback'));
  });
}
