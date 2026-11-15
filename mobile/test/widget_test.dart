import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:loop_mobile/api.dart';
import 'package:loop_mobile/main.dart';
import 'package:loop_mobile/models.dart';
import 'package:loop_mobile/store.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_api.dart';

FakeApi fixtureApi() {
  final api = FakeApi();
  api.listings['/tmp/ws'] = {
    'path': '/tmp/ws',
    'parent': null,
    'roots': api.dirsData['roots'],
    'dirs': [
      {'name': 'src', 'path': '/tmp/ws/src'}
    ],
  };
  api.listings['/tmp/ws/src'] = {
    'path': '/tmp/ws/src',
    'parent': '/tmp/ws',
    'roots': api.dirsData['roots'],
    'dirs': [],
  };
  api.snapshotData = {
    'daemon': {'state': 'running'},
    'current': {
      'id': 'run-1',
      'task': 'running task',
      'state': 'running',
      'turns': 2,
      'cost': 0.25,
    },
    'queue': [
      {'id': 'q000001', 'text': 'queued work', 'state': 'queued'}
    ],
    'done': [
      {
        'id': 'run-2',
        'task': 'done work',
        'state': 'complete',
        'turns': 4,
        'cost': 1.5,
        'finish': 'done'
      }
    ],
    'costs': {'total': 1.75},
  };
  api.logData = {
    'id': 'run-1',
    'state': 'complete',
    'turns': 1,
    'terminal': true,
    'entries': [
      {'kind': 'call', 'turn': 1, 'name': 'exec', 'args': '["ls"]', 'obs': 'ok'},
      {'kind': 'result', 'result': 'the final summary', 'finish': 'done'}
    ],
  };
  return api;
}

Future<void> connect(WidgetTester tester) async {
  await tester.enterText(find.byKey(const Key('host-field')), '127.0.0.1');
  await tester.enterText(find.byKey(const Key('port-field')), '8787');
  await tester.enterText(find.byKey(const Key('token-field')), 't0ken');
  await tester.tap(find.byKey(const Key('connect-button')));
  await tester.pumpAndSettle();
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('saved connection auto-logs in on launch', (tester) async {
    final api = fixtureApi();
    const saved =
        ConnectionSettings(host: '127.0.0.1', port: 8787, token: 't0ken');
    final store = LoopStore(
        apiFactory: (_) => api,
        pollInterval: const Duration(hours: 1),
        saved: saved);
    addTearDown(store.dispose);
    await tester.pumpWidget(LoopApp(store: store, saved: saved));
    await tester.pumpAndSettle();
    expect(find.text('running task'), findsOneWidget);
    expect(find.byKey(const Key('host-field')), findsNothing);
    expect(store.online, isTrue);
  });

  testWidgets('connect, choose a directory, submit, and open live logs', (tester) async {
    final api = fixtureApi();
    final store = LoopStore(apiFactory: (_) => api, pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    await tester.pumpWidget(LoopApp(store: store));
    expect(find.text('connect'), findsOneWidget);
    await connect(tester);

    expect(find.text('daemon running'), findsOneWidget);
    expect(find.text('running task'), findsOneWidget);
    expect(find.text('queued work'), findsOneWidget);
    expect(find.text('done work'), findsOneWidget);
    expect(find.text('queued: 1'), findsOneWidget);
    expect(find.text('done: 1'), findsOneWidget);

    await tester.tap(find.byKey(const Key('browse-button')));
    await tester.pumpAndSettle();
    expect(find.text('src'), findsOneWidget);
    await tester.tap(find.text('src'));
    await tester.pumpAndSettle();
    expect(find.text('/tmp/ws/src'), findsOneWidget);
    await tester.tap(find.byKey(const Key('use-directory-button')));
    await tester.pumpAndSettle();
    expect(find.text('/tmp/ws/src'), findsOneWidget);

    await tester.enterText(find.byKey(const Key('task-field')), 'new task');
    await tester.tap(find.byKey(const Key('queue-button')));
    await tester.pumpAndSettle();
    expect(api.enqueuedTask, 'new task');
    expect(api.enqueuedRoot, '/tmp/ws/src');

    await tester.tap(find.text('running task'));
    await tester.pumpAndSettle();
    expect(find.textContaining('id=run-1'), findsOneWidget);
    expect(find.text('✓ result'), findsOneWidget);
    expect(find.text('the final summary'), findsOneWidget);
    expect(find.textContaining('t1 exec', findRichText: true), findsOneWidget);
  });

  testWidgets('current run state wins over a stale interrupted log', (tester) async {
    final api = fixtureApi();
    api.logData = {
      'id': 'run-1',
      'state': 'interrupted',
      'turns': 2,
      'terminal': false,
      'entries': [
        {'kind': 'pending', 'text': 'summary pending'}
      ],
    };
    final store = LoopStore(apiFactory: (_) => api, pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    await tester.pumpWidget(LoopApp(store: store));
    await connect(tester);
    await tester.tap(find.text('running task'));
    await tester.pumpAndSettle();
    expect(find.textContaining('state=running'), findsOneWidget);
    expect(find.textContaining('state=interrupted'), findsNothing);
  });

  testWidgets('connection failure is visible and does not invent a task', (tester) async {
    final api = fixtureApi()
      ..failWith = const LoopApiException(ApiFailure.network, 'connection refused');
    final store = LoopStore(apiFactory: (_) => api, pollInterval: const Duration(hours: 1));
    addTearDown(store.dispose);
    await tester.pumpWidget(LoopApp(store: store));
    await connect(tester);
    expect(find.text('daemon offline'), findsOneWidget);
    expect(find.text('✕ connection refused'), findsOneWidget);
    expect(find.text('running task'), findsNothing);
  });
}
