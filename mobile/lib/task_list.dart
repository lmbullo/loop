/// The scrollable task list: workspace and running/queued/done groups.
///
/// The prompt is fixed at the bottom by the home shell, so the list owns all
/// remaining height and never overlaps the keyboard.
library;

import 'package:material_ui/material_ui.dart';

import 'store.dart';
import 'task_rows.dart';
import 'theme.dart';
import 'widgets.dart';

class TaskList extends StatelessWidget {
  const TaskList({
    super.key,
    required this.store,
    required this.onBrowse,
    required this.onOpenRun,
  });

  final LoopStore store;
  final VoidCallback onBrowse;
  final ValueChanged<String> onOpenRun;

  @override
  Widget build(BuildContext context) {
    final snapshot = store.snapshot;
    return RefreshIndicator(
      color: LoopColors.accent,
      backgroundColor: LoopColors.panel,
      onRefresh: store.refresh,
      child: ListView(
        key: const Key('task-list'),
        physics: const AlwaysScrollableScrollPhysics(),
        keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
        padding: const EdgeInsets.only(bottom: 20),
        children: [
          _Workspace(store: store, onBrowse: onBrowse),
          _group('active', [
            if (snapshot.current == null)
              const EmptyLine(text: 'no active run')
            else
              TaskRow(
                key: Key('task-${snapshot.current!.runId}'),
                item: snapshot.current!,
                onTap: () => onOpenRun(snapshot.current!.runId),
              ),
          ]),
          if (snapshot.queue.isNotEmpty)
            _group('queued · ${snapshot.queue.length}', [
              for (final item in snapshot.queue)
                QueueRow(key: Key('queue-${item.id}'), item: item),
            ]),
          _group('done · ${snapshot.done.length}', [
            if (snapshot.done.isEmpty)
              const EmptyLine(text: 'no completed runs')
            else
              for (final item in snapshot.done)
                TaskRow(
                  key: Key('task-${item.runId}'),
                  item: item,
                  onTap: () => onOpenRun(item.runId),
                ),
          ]),
        ],
      ),
    );
  }

  Widget _group(String title, List<Widget> children) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      SectionHeader(label: title),
      ...children,
    ],
  );
}

class _Workspace extends StatelessWidget {
  const _Workspace({required this.store, required this.onBrowse});

  final LoopStore store;
  final VoidCallback onBrowse;

  @override
  Widget build(BuildContext context) {
    final root = store.selectedRoot;
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 8, 4),
      child: Row(
        children: [
          const Text('workspace', style: TextStyle(color: LoopColors.muted)),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              root == null || root.isEmpty ? 'not selected' : root,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: root == null ? LoopColors.warn : LoopColors.strong,
                fontSize: 12,
              ),
            ),
          ),
          TextButton(
            key: const Key('browse-button'),
            onPressed: store.loadingDirs ? null : onBrowse,
            child: Text(store.loadingDirs ? '…' : 'browse'),
          ),
        ],
      ),
    );
  }
}
