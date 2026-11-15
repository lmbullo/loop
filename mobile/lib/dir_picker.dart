/// Allowlisted directory browser; the server decides which paths exist.
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
        final title = _path == null ? 'roots' : _basename(_path!);
        return Scaffold(
          appBar: AppBar(title: Text('workspace · $title')),
          body: Column(
            children: [
              _PathBar(path: _path),
              if (store.error != null) ErrorBanner(text: store.error!),
              Expanded(
                child: ListView(
                  children: [
                    if (listing.path != null && listing.parent != null)
                      _DirRow(
                        name: '..',
                        path: listing.parent!,
                        label: listing.parent!,
                        onTap: () => _open(listing.parent!),
                      ),
                    if (listing.path == null)
                      for (final entry in listing.roots) _rootRow(entry)
                    else
                      for (final entry in listing.dirs) _dirRow(entry),
                    if (listing.path != null && listing.dirs.isEmpty)
                      const EmptyLine(text: 'no subdirectories'),
                    if (listing.truncated)
                      const EmptyLine(text: 'listing truncated'),
                  ],
                ),
              ),
              _footer(listing),
            ],
          ),
        );
      },
    );
  }

  Widget _footer(DirListing listing) {
    return Container(
      padding: const EdgeInsets.fromLTRB(LoopSpace.lg, 10, LoopSpace.lg, 10),
      decoration: const BoxDecoration(
        border: Border(top: BorderSide(color: LoopColors.line)),
      ),
      child: Row(
        children: [
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
    );
  }

  Widget _rootRow(DirEntry entry) => _DirRow(
    name: entry.name,
    path: entry.path,
    label: entry.path,
    onTap: () => _open(entry.path),
  );

  Widget _dirRow(DirEntry entry) => _DirRow(
    name: entry.name,
    path: entry.path,
    label: entry.path,
    onTap: () => _open(entry.path),
  );

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
      padding: const EdgeInsets.fromLTRB(LoopSpace.lg, 10, LoopSpace.lg, 10),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: Row(
        children: [
          const Text('path', style: LoopType.label),
          const SizedBox(width: LoopSpace.md),
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
    return Material(
      key: ValueKey('dir:$path'),
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        child: Container(
          padding: const EdgeInsets.fromLTRB(
            LoopSpace.lg,
            11,
            LoopSpace.md,
            11,
          ),
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: LoopColors.line)),
          ),
          child: Row(
            children: [
              Text(
                name == '..' ? '↑' : '▸',
                style: const TextStyle(
                  color: LoopColors.faint,
                  fontSize: 12,
                  height: 1.2,
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
                      style: name == '..'
                          ? const TextStyle(
                              color: LoopColors.muted,
                              fontSize: 13,
                            )
                          : LoopType.task.copyWith(fontSize: 14),
                    ),
                    if (label != name) ...[
                      const SizedBox(height: 2),
                      Text(
                        label,
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: const TextStyle(
                          color: LoopColors.faint,
                          fontSize: 10.5,
                        ),
                      ),
                    ],
                  ],
                ),
              ),
              const Padding(
                padding: EdgeInsets.only(left: LoopSpace.sm),
                child: Text(
                  '›',
                  style: TextStyle(
                    color: LoopColors.faint,
                    fontSize: 16,
                    height: 1,
                  ),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
