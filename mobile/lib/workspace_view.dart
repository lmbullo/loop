/// Workspace view: roots, the active directory, bridge details and sign-out.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'store.dart';
import 'theme.dart';
import 'widgets.dart';
import 'workspace_rows.dart';

class WorkspaceView extends StatelessWidget {
  const WorkspaceView({
    super.key,
    required this.store,
    required this.onBrowse,
    required this.onConfig,
    required this.onDisconnect,
  });

  final LoopStore store;
  final VoidCallback onBrowse;
  final VoidCallback onConfig;
  final VoidCallback onDisconnect;

  @override
  Widget build(BuildContext context) {
    final selected = store.selectedRoot;
    final settings = store.settings;
    return ListView(
      key: const Key('workspace-list'),
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.sm,
        LoopSpace.lg,
        LoopSpace.lg,
      ),
      children: [
        const Text('workspace', style: LoopType.hero),
        const SizedBox(height: 4),
        Text(
          selected == null ? 'choose where the agent may work' : selected,
          maxLines: 2,
          overflow: TextOverflow.ellipsis,
          style: LoopType.meta,
        ),
        const SizedBox(height: LoopSpace.md),
        if (store.workspaces.isNotEmpty)
          Padding(
            padding: const EdgeInsets.only(bottom: LoopSpace.sm),
            child: Text(
              '${store.workspaces.length} workspaces · '
              '\$${store.workspaces.fold<double>(0, (sum, item) => sum + (item.cost ?? 0)).toStringAsFixed(6)} total',
              key: const Key('workspace-aggregate'),
              style: LoopType.meta.copyWith(color: LoopColors.faint),
            ),
          ),
        LoopCard(
          color: LoopColors.surface,
          borderColor: selected == null
              ? LoopColors.warn.withValues(alpha: 0.4)
              : LoopColors.aqua.withValues(alpha: 0.35),
          child: Row(
            children: [
              Container(
                width: 42,
                height: 42,
                decoration: BoxDecoration(
                  color: LoopColors.aqua.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(LoopRadius.md),
                ),
                child: const Icon(
                  Icons.folder_open_rounded,
                  color: LoopColors.aqua,
                  size: 22,
                ),
              ),
              const SizedBox(width: LoopSpace.md),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('active root', style: LoopType.label),
                    const SizedBox(height: 3),
                    Text(
                      selected ?? 'not selected',
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: LoopType.task.copyWith(fontSize: 13),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: LoopSpace.sm),
        SizedBox(
          width: double.infinity,
          child: OutlinedButton.icon(
            key: const Key('workspace-browse'),
            onPressed: onBrowse,
            icon: const Icon(Icons.folder_copy_outlined, size: 18),
            label: const Text('browse allowlisted directories'),
          ),
        ),
        const SectionHeader(label: 'bridge'),
        LoopCard(
          color: LoopColors.surface,
          child: Column(
            children: [
              _InfoRow(
                icon: Icons.lan_outlined,
                label: 'address',
                value: settings?.label ?? 'not connected',
              ),
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 10),
                child: Hairline(),
              ),
              const _InfoRow(
                icon: Icons.shield_outlined,
                label: 'transport',
                value: 'private network · bearer token',
                tone: LoopColors.aqua,
              ),
              const Padding(
                padding: EdgeInsets.symmetric(vertical: 10),
                child: Hairline(),
              ),
              _InfoRow(
                icon: Icons.memory_rounded,
                label: 'daemon',
                value: store.statusState,
                tone: statusColor(store.statusState),
              ),
              const SizedBox(height: LoopSpace.md),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  key: const Key('workspace-config'),
                  onPressed: onConfig,
                  icon: const Icon(Icons.tune_rounded, size: 18),
                  label: const Text('connection settings'),
                ),
              ),
            ],
          ),
        ),
        if (store.workspaces.isNotEmpty) ...[
          const SectionHeader(label: 'workspaces'),
          for (final item in store.workspaces)
            WorkspaceRow(
              item: item,
              selected: item.path == selected || item.path == store.snapshot.tree,
              onSelect: () => store.selectRoot(item.path),
              onStart: () => store.startWorkspace(item.path),
            ),
        ],
        if (store.listing.roots.isNotEmpty) ...[
          const SectionHeader(label: 'allowed roots'),
          for (final entry in store.listing.roots)
            _RootTile(
              entry: entry,
              selected: entry.path == selected,
              onTap: () => store.selectRoot(entry.path),
            ),
        ],
        const SizedBox(height: LoopSpace.lg),
        TextButton(
          key: const Key('disconnect-button'),
          onPressed: onDisconnect,
          child: const Text('disconnect and forget session'),
        ),
      ],
    );
  }
}

class _RootTile extends StatelessWidget {
  const _RootTile({
    required this.entry,
    required this.selected,
    required this.onTap,
  });

  final DirEntry entry;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: LoopSpace.sm),
      child: LoopCard(
        key: ValueKey('root-${entry.path}'),
        onTap: onTap,
        color: selected ? LoopColors.bg0Soft : LoopColors.surface,
        borderColor: selected
            ? LoopColors.aqua.withValues(alpha: 0.4)
            : LoopColors.line,
        padding: const EdgeInsets.fromLTRB(13, 11, 11, 11),
        child: Row(
          children: [
            Icon(
              selected ? Icons.folder_rounded : Icons.folder_outlined,
              color: selected ? LoopColors.aqua : LoopColors.muted,
              size: 19,
            ),
            const SizedBox(width: LoopSpace.md),
            Expanded(
              child: Text(
                entry.path,
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: LoopType.body.copyWith(
                  color: selected ? LoopColors.strong : LoopColors.body,
                ),
              ),
            ),
            if (selected)
              const Icon(
                Icons.check_circle_rounded,
                color: LoopColors.aqua,
                size: 18,
              ),
          ],
        ),
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.icon,
    required this.label,
    required this.value,
    this.tone = LoopColors.body,
  });

  final IconData icon;
  final String label;
  final String value;
  final Color tone;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 17, color: LoopColors.muted),
        const SizedBox(width: LoopSpace.sm),
        Text(label, style: LoopType.meta.copyWith(color: LoopColors.faint)),
        const SizedBox(width: LoopSpace.md),
        Expanded(
          child: Text(
            value,
            maxLines: 1,
            overflow: TextOverflow.ellipsis,
            textAlign: TextAlign.end,
            style: TextStyle(color: tone, fontSize: 12),
          ),
        ),
      ],
    );
  }
}
