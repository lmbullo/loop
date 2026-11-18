import 'package:material_ui/material_ui.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:loop_mobile/main.dart';
import 'package:loop_mobile/store.dart';
import 'package:loop_mobile/theme.dart';
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

  test('the palette is Gruvbox dark', () {
    expect(LoopColors.background, const Color(0xFF1D2021));
    expect(LoopColors.surface, const Color(0xFF282828));
    expect(LoopColors.strong, const Color(0xFFEBDBB2));
    expect(LoopColors.accent, const Color(0xFFFE8019));
    expect(LoopColors.ok, const Color(0xFFB8BB26));
    expect(LoopColors.error, const Color(0xFFFB4934));
  });

  testWidgets('floating prompt and nav clear the system inset', (tester) async {
    tester.view.physicalSize = const Size(360, 800);
    tester.view.devicePixelRatio = 1.0;
    tester.view.padding = const FakeViewPadding(bottom: 24);
    addTearDown(tester.view.reset);

    await pumpHome(tester);

    expect(find.byKey(const Key('bottom-nav')), findsOneWidget);
    expect(find.byKey(const Key('nav-tasks')), findsOneWidget);
    expect(find.byKey(const Key('nav-activity')), findsOneWidget);
    expect(find.byKey(const Key('nav-workspace')), findsOneWidget);
    expect(find.byKey(const Key('activity-list')), findsNothing);

    final prompt = find.byKey(const Key('prompt-box'));
    expect(prompt, findsOneWidget);
    final promptShell = tester.widget<AnimatedContainer>(prompt);
    final promptDecoration = promptShell.decoration! as BoxDecoration;
    expect(promptDecoration.borderRadius, BorderRadius.circular(24));

    final promptRect = tester.getRect(prompt);
    expect(promptRect.left, 16);
    expect(promptRect.right, 344);
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

    final nav = find.byKey(const Key('bottom-nav'));
    final navShell = tester.widget<Container>(nav);
    final navDecoration = navShell.decoration! as BoxDecoration;
    expect(navDecoration.borderRadius, BorderRadius.circular(24));
    expect(tester.getSize(nav).height, 68);
    final navRect = tester.getRect(nav);
    expect(navRect.left, 16);
    expect(navRect.right, 344);
    expect(navRect.bottom, lessThanOrEqualTo(800 - 24));
    expect(promptRect.bottom, lessThan(navRect.top));

    final listRect = tester.getRect(find.byKey(const Key('task-list')));
    expect(listRect.bottom, lessThanOrEqualTo(promptRect.top));
  });

  testWidgets('floating nav switches to the activity timeline', (tester) async {
    await pumpHome(tester);

    await tester.tap(find.byKey(const Key('nav-activity')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('activity-list')), findsOneWidget);
    expect(find.text('recent tasks'), findsOneWidget);
    expect(find.text('done work'), findsOneWidget);
    expect(find.byKey(const Key('prompt-box')), findsNothing);

    await tester.tap(find.byKey(const Key('nav-tasks')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('prompt-box')), findsOneWidget);
    expect(find.byKey(const Key('activity-list')), findsNothing);
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

    expect(find.byKey(const Key('bottom-nav')), findsNothing);
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

  testWidgets('opening the keyboard keeps the composer focused', (
    tester,
  ) async {
    tester.view.physicalSize = const Size(400, 800);
    tester.view.devicePixelRatio = 1.0;
    addTearDown(tester.view.reset);

    await pumpHome(tester);
    final field = find.byKey(const Key('task-field'));
    await tester.tap(field);
    await tester.pump();
    expect(tester.widget<TextField>(field).focusNode?.hasFocus, isTrue);

    tester.view.viewInsets = const FakeViewPadding(bottom: 300);
    await tester.pumpAndSettle();

    expect(find.byKey(const Key('bottom-nav')), findsNothing);
    expect(tester.widget<TextField>(field).focusNode?.hasFocus, isTrue);
  });

  testWidgets('task rows lead with task text and status, not metadata', (
    tester,
  ) async {
    await pumpHome(tester);

    final row = find.byKey(const Key('task-run-1'));
    await tester.dragUntilVisible(
      row,
      find.byKey(const Key('task-list')),
      const Offset(0, -120),
    );
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

    expect(tester.getSize(row).height, greaterThanOrEqualTo(64));

    final doneRow = find.byKey(const Key('task-run-2'));
    await tester.dragUntilVisible(
      doneRow,
      find.byKey(const Key('task-list')),
      const Offset(0, -160),
    );
    expect(doneRow, findsOneWidget);
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
      await tester.dragUntilVisible(
        row,
        find.byKey(const Key('task-list')),
        const Offset(0, -120),
      );
      expect(row, findsOneWidget);
      expect(tester.getSize(row).height, lessThan(120));
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
