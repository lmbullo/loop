import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:loop_mobile/main.dart';
import 'package:loop_mobile/store.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'fake_api.dart';

FakeApi layoutApi({String currentTask = 'running task'}) {
  final api = FakeApi();
  api.snapshotData = {
    'daemon': {'state': 'running'},
    'current': {
      'id': 'run-1',
      'task': currentTask,
      'state': 'running',
      'turns': 2,
      'cost': 0.25,
    },
    'queue': [
      {'id': 'q000001', 'text': 'queued work', 'state': 'queued'},
    ],
    'done': [
      {
        'id': 'run-2',
        'task': 'done work',
        'state': 'complete',
        'turns': 4,
        'cost': 1.5,
        'finish': 'done',
      },
    ],
    'costs': {'total': 1.75},
  };
  return api;
}

Future<LoopStore> pumpHome(WidgetTester tester, {FakeApi? api}) async {
  final store = LoopStore(
    apiFactory: (_) => api ?? layoutApi(),
    pollInterval: const Duration(hours: 1),
  );
  addTearDown(store.dispose);
  await tester.pumpWidget(LoopApp(store: store));
  await tester.enterText(find.byKey(const Key('host-field')), '127.0.0.1');
  await tester.enterText(find.byKey(const Key('port-field')), '8787');
  await tester.enterText(find.byKey(const Key('token-field')), 't0ken');
  await tester.tap(find.byKey(const Key('connect-button')));
  await tester.pumpAndSettle();
  return store;
}

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  testWidgets('bottom prompt is sharp and clears the system inset', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    tester.view.padding = const FakeViewPadding(bottom: 24);
    addTearDown(tester.view.reset);

    await pumpHome(tester);

    expect(find.byKey(const Key('bottom-nav')), findsNothing);
    expect(find.byKey(const Key('nav-tasks')), findsNothing);
    expect(find.byKey(const Key('nav-activity')), findsNothing);
    expect(find.byKey(const Key('activity-list')), findsNothing);

    final prompt = find.byKey(const Key('prompt-box'));
    expect(prompt, findsOneWidget);
    final decoration =
        tester.widget<Container>(prompt).decoration! as BoxDecoration;
    expect(decoration.borderRadius, BorderRadius.zero);

    final promptRect = tester.getRect(prompt);
    expect(promptRect.left, 12);
    expect(promptRect.right, 348);
    expect(promptRect.bottom, moreOrLessEquals(800 - 24 - 12));
    expect(
      find.descendant(
        of: prompt,
        matching: find.byKey(const Key('task-field')),
      ),
      findsOneWidget,
    );
    expect(
      find.descendant(
        of: prompt,
        matching: find.byKey(const Key('queue-button')),
      ),
      findsOneWidget,
    );

    final listRect = tester.getRect(find.byKey(const Key('task-list')));
    expect(listRect.bottom, lessThanOrEqualTo(promptRect.top));
  });

  testWidgets('bottom prompt stays above the keyboard on a small phone', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(320, 480);
    tester.view.devicePixelRatio = 1.0;
    tester.view.padding = const FakeViewPadding(bottom: 24);
    addTearDown(tester.view.reset);

    await pumpHome(tester);
    tester.view.viewInsets = const FakeViewPadding(bottom: 200);
    await tester.pumpAndSettle();

    final promptRect = tester.getRect(find.byKey(const Key('prompt-box')));
    expect(promptRect.top, greaterThan(0));
    expect(promptRect.bottom, lessThanOrEqualTo(480 - 200));
    final listRect = tester.getRect(find.byKey(const Key('task-list')));
    expect(listRect.bottom, lessThanOrEqualTo(promptRect.top));

    await tester.enterText(
      find.byKey(const Key('task-field')),
      'a long prompt that wraps over several lines without hiding the queue button',
    );
    await tester.pumpAndSettle();
    final grown = tester.getRect(find.byKey(const Key('prompt-box')));
    expect(grown.bottom, lessThanOrEqualTo(480 - 200));
    expect(find.byKey(const Key('queue-button')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  testWidgets('task rows lead with task text and status, not metadata', (
    tester,
  ) async {
    await pumpHome(tester);

    final row = find.byKey(const Key('task-run-1'));
    expect(row, findsOneWidget);
    expect(
      find.descendant(of: row, matching: find.text('running task')),
      findsOneWidget,
    );
    expect(
      find.descendant(of: row, matching: find.text('running')),
      findsOneWidget,
    );
    for (final meta in ['id=run-1', 'turns=2', 'cost=', 'finish=']) {
      expect(
        find.descendant(of: row, matching: find.textContaining(meta)),
        findsNothing,
      );
    }
    expect(find.textContaining('cost='), findsNothing);
    expect(find.textContaining('roots='), findsNothing);

    final doneRow = find.byKey(const Key('task-run-2'));
    expect(
      find.descendant(of: doneRow, matching: find.text('done')),
      findsNothing,
    );
    expect(tester.getSize(row).height, greaterThanOrEqualTo(64));
  });

  testWidgets(
    'long task text truncates and the list scrolls without overflow',
    (tester) async {
      tester.view.physicalSize = const Size(320, 480);
      tester.view.devicePixelRatio = 1.0;
      tester.view.padding = const FakeViewPadding(bottom: 24);
      addTearDown(tester.view.reset);

      final api = layoutApi(currentTask: 'current task ' * 40);
      api.snapshotData['done'] = [
        for (var i = 0; i < 12; i++)
          {
            'id': 'done-$i',
            'task': 'finished task $i ' * 30,
            'state': 'complete',
            'turns': i,
            'cost': 0.01,
            'finish': 'done',
          },
      ];
      await pumpHome(tester, api: api);

      final row = find.byKey(const Key('task-run-1'));
      expect(row, findsOneWidget);
      expect(tester.getSize(row).height, lessThan(100));
      expect(tester.takeException(), isNull);

      await tester.drag(
        find.byKey(const Key('task-list')),
        const Offset(0, -300),
      );
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('prompt-box')), findsOneWidget);
      expect(tester.takeException(), isNull);
    },
  );
}
