/// Allowlisted directory browser with a floating path and use footer.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'store.dart';
import 'theme.dart';
import 'widgets.dart';

class DirPickerScreen extends StatefulWidget {
  const DirPickerScreen({super.key, required this.store});

  final LoopStore store;

  @override
  State<DirPickerScreen> createState() => _DirPickerScreenState();
}

class _DirPickerScreenState extends State<DirPickerScreen> {
  String? _path;

  @override
  void initState() {
    super.initState();
    _path = widget.store.selectedRoot;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.store.browse(_path);
    });
  }

  void _open(String path) {
    setState(() => _path = path);
    widget.store.browse(path);
  }

  void _use() {
    final path = widget.store.listing.path;
    if (path == null) return;
    widget.store.selectRoot(path);
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) {
        final store = widget.store;
        final listing = store.listing;
        return Scaffold(
          appBar: AppBar(
            title: const Text('workspace'),
            actions: const [
              Padding(
                padding: EdgeInsets.only(right: LoopSpace.lg),
                child: Icon(
                  Icons.folder_open_rounded,
                  color: LoopColors.accent,
                  size: 20,
                ),
              ),
            ],
          ),
          body: LoopBackdrop(
            child: SafeArea(
              top: false,
              child: Column(
                children: [
                  _PathBar(path: _path),
                  if (store.error != null) ErrorBanner(text: store.error!),
                  Expanded(
                    child: ListView(
                      key: const Key('dir-list'),
                      padding: const EdgeInsets.fromLTRB(
                        LoopSpace.lg,
                        LoopSpace.xs,
                        LoopSpace.lg,
                        LoopSpace.lg,
                      ),
                      children: [
                        if (listing.path != null && listing.parent != null)
                          _DirRow(
                            name: '..',
                            path: listing.parent!,
                            label: 'parent',
                            onTap: () => _open(listing.parent!),
                          ),
                        if (listing.path == null)
                          for (final entry in listing.roots)
                            _DirRow(
                              name: entry.name,
                              path: entry.path,
                              label: entry.path,
                              onTap: () => _open(entry.path),
                            )
                        else
                          for (final entry in listing.dirs)
                            _DirRow(
                              name: entry.name,
                              path: entry.path,
                              label: entry.path,
                              onTap: () => _open(entry.path),
                            ),
                        if (listing.path != null && listing.dirs.isEmpty)
                          const EmptyState(
                            icon: Icons.folder_off_outlined,
                            title: 'no subdirectories',
                            body:
                                'Use this directory or go back up to choose '
                                'another allowlisted root.',
                          ),
                        if (listing.truncated)
                          const EmptyLine(text: 'listing truncated'),
                      ],
                    ),
                  ),
                  _footer(listing),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _footer(DirListing listing) {
    final inset = MediaQuery.paddingOf(context).bottom;
    return Padding(
      padding: EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.xs,
        LoopSpace.lg,
        LoopSpace.md + inset,
      ),
      child: Container(
        padding: const EdgeInsets.fromLTRB(14, 10, 10, 10),
        decoration: BoxDecoration(
          color: LoopColors.panel,
          borderRadius: BorderRadius.circular(LoopRadius.lg),
          border: Border.all(color: LoopColors.lineStrong),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.35),
              blurRadius: 22,
              offset: const Offset(0, 8),
            ),
          ],
        ),
        child: Row(
          children: [
            const Icon(Icons.place_outlined, size: 17, color: LoopColors.aqua),
            const SizedBox(width: LoopSpace.sm),
            Expanded(
              child: Text(
                listing.path == null
                    ? 'select a root first'
                    : 'use ${_basename(listing.path!)}',
                style: LoopType.meta.copyWith(fontSize: 11),
                overflow: TextOverflow.ellipsis,
              ),
            ),
            const SizedBox(width: LoopSpace.sm),
            FilledButton(
              key: const Key('use-directory-button'),
              onPressed: listing.path == null ? null : _use,
              child: const Text('use directory'),
            ),
          ],
        ),
      ),
    );
  }

  static String _basename(String path) {
    final clean = path.endsWith('/')
        ? path.substring(0, path.length - 1)
        : path;
    final index = clean.lastIndexOf('/');
    return index < 0 ? clean : clean.substring(index + 1);
  }
}

class _PathBar extends StatelessWidget {
  const _PathBar({required this.path});

  final String? path;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      margin: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.xs,
        LoopSpace.lg,
        LoopSpace.xs,
      ),
      padding: const EdgeInsets.fromLTRB(13, 11, 13, 11),
      decoration: BoxDecoration(
        color: LoopColors.surface,
        borderRadius: BorderRadius.circular(LoopRadius.md),
        border: Border.all(color: LoopColors.line),
      ),
      child: Row(
        children: [
          const Icon(
            Icons.route_rounded,
            size: 17,
            color: LoopColors.accentSoft,
          ),
          const SizedBox(width: LoopSpace.sm),
          Expanded(
            child: Text(
              path ?? 'choose an allowed root',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                color: path == null ? LoopColors.faint : LoopColors.body,
                fontSize: 11.5,
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _DirRow extends StatelessWidget {
  const _DirRow({
    required this.name,
    required this.path,
    required this.label,
    required this.onTap,
  });

  final String name;
  final String path;
  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final parent = name == '..';
    return Padding(
      padding: const EdgeInsets.only(bottom: LoopSpace.sm),
      child: LoopCard(
        key: ValueKey('dir:$path'),
        onTap: onTap,
        color: LoopColors.surface,
        padding: const EdgeInsets.fromLTRB(13, 12, 11, 12),
        child: Row(
          children: [
            Container(
              width: 34,
              height: 34,
              decoration: BoxDecoration(
                color: (parent ? LoopColors.warn : LoopColors.aqua).withValues(
                  alpha: 0.09,
                ),
                borderRadius: BorderRadius.circular(LoopRadius.sm),
              ),
              child: Icon(
                parent ? Icons.arrow_upward_rounded : Icons.folder_rounded,
                size: 18,
                color: parent ? LoopColors.warn : LoopColors.aqua,
              ),
            ),
            const SizedBox(width: LoopSpace.md),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    name,
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                    style: parent
                        ? LoopType.meta.copyWith(color: LoopColors.muted)
                        : LoopType.task.copyWith(fontSize: 14),
                  ),
                  if (label != name) ...[
                    const SizedBox(height: 2),
                    Text(
                      label,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: LoopType.caption.copyWith(letterSpacing: 0),
                    ),
                  ],
                ],
              ),
            ),
            const Icon(
              Icons.chevron_right_rounded,
              size: 20,
              color: LoopColors.faint,
            ),
          ],
        ),
      ),
    );
  }
}
