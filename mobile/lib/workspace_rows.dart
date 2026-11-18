/// Discovered workspace rows: state, queue/done/cost and an explicit start.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

class WorkspaceRow extends StatelessWidget {
  const WorkspaceRow({
    super.key,
    required this.item,
    required this.selected,
    required this.onSelect,
    required this.onStart,
  });

  final WorkspaceItem item;
  final bool selected;
  final VoidCallback onSelect;
  final VoidCallback onStart;

  @override
  Widget build(BuildContext context) {
    final tone = statusColor(item.state);
    return Padding(
      padding: const EdgeInsets.only(bottom: LoopSpace.sm),
      child: LoopCard(
        key: ValueKey('workspace-${item.path}'),
        onTap: onSelect,
        color: selected ? LoopColors.bg0Soft : LoopColors.surface,
        borderColor: selected
            ? LoopColors.aqua.withValues(alpha: 0.45)
            : LoopColors.line,
        padding: const EdgeInsets.fromLTRB(13, 11, 11, 11),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                Icon(
                  selected ? Icons.folder_rounded : Icons.folder_outlined,
                  color: selected ? LoopColors.aqua : LoopColors.muted,
                  size: 19,
                ),
                const SizedBox(width: LoopSpace.sm),
                Expanded(
                  child: Text(
                    item.name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: LoopType.body.copyWith(
                      color: selected ? LoopColors.strong : LoopColors.body,
                    ),
                  ),
                ),
                Text(
                  item.state,
                  style: LoopType.caption.copyWith(color: tone),
                ),
              ],
            ),
            const SizedBox(height: 5),
            Text(
              item.path,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: LoopType.caption.copyWith(color: LoopColors.faint),
            ),
            const SizedBox(height: 7),
            Row(
              children: [
                _Meta(label: 'run', value: '${item.running}'),
                _Meta(label: 'queue', value: '${item.queued}'),
                _Meta(label: 'done', value: '${item.done}'),
                _Meta(label: 'cost', value: item.costLabel),
                if (item.canStart)
                  TextButton(
                    key: ValueKey('start-${item.path}'),
                    onPressed: onStart,
                    child: const Text('start'),
                  )
                else if (selected)
                  const Icon(
                    Icons.check_circle_rounded,
                    color: LoopColors.aqua,
                    size: 18,
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}

class _Meta extends StatelessWidget {
  const _Meta({required this.label, required this.value});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Expanded(
      child: Text(
        '$label $value',
        maxLines: 1,
        overflow: TextOverflow.ellipsis,
        style: LoopType.caption.copyWith(color: LoopColors.muted),
      ),
    );
  }
}
