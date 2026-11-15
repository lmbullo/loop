/// Main screen: connection status, workspace choice, composer and task lists.
library;

import 'package:material_ui/material_ui.dart';

import 'connect_pane.dart';
import 'dir_picker.dart';
import 'models.dart';
import 'run_screen.dart';
import 'session.dart';
import 'store.dart';
import 'theme.dart';
import 'widgets.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key, required this.store, this.saved});

  final LoopStore store;
  final ConnectionSettings? saved;

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _task = TextEditingController();
  bool _editingConnection = false;

  @override
  void initState() {
    super.initState();
    _editingConnection = !widget.store.connected;
    final saved = widget.saved;
    if (saved != null) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && !widget.store.connected) {
          _connect(saved.host, saved.port, saved.token);
        }
      });
    }
  }

  @override
  void dispose() {
    _task.dispose();
    super.dispose();
  }

  Future<bool> _connect(String host, int port, String token) async {
    final ok = await widget.store.connect(host, port, token);
    if (ok) await Session.save(widget.store.settings!);
    if (!mounted) return ok;
    if (widget.store.connected) setState(() => _editingConnection = false);
    return ok;
  }

  Future<void> _submit() async {
    final ok = await widget.store.submitTask(_task.text);
    if (ok && mounted) _task.clear();
  }

  void _openRun(String runId) {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => RunScreen(store: widget.store, runId: runId),
    ));
  }

  void _browse() {
    Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => DirPickerScreen(store: widget.store),
    ));
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) {
        final store = widget.store;
        final form = _editingConnection || !store.connected;
        return Scaffold(
          body: SafeArea(
            child: form
                ? ConnectPane(
                    initial: store.settings,
                    error: store.error,
                    onConnect: _connect,
                    onCancel: store.connected
                        ? () => setState(() => _editingConnection = false)
                        : null,
                  )
                : _body(context, store),
          ),
        );
      },
    );
  }

  Widget _body(BuildContext context, LoopStore store) {
    final snapshot = store.snapshot;
    return Column(
      children: [
        StatusBar(
          state: store.statusState,
          detail: store.statusDetail,
          trailing: TextButton(
            key: const Key('config-button'),
            onPressed: () => setState(() => _editingConnection = true),
            child: const Text('config'),
          ),
        ),
        if (store.error != null) ErrorBanner(text: store.error!),
        Expanded(
          child: RefreshIndicator(
            color: LoopColors.accent,
            backgroundColor: LoopColors.panel,
            onRefresh: store.refresh,
            child: ListView(
              physics: const AlwaysScrollableScrollPhysics(),
              padding: const EdgeInsets.only(bottom: 24),
              children: [
                _workspace(store),
                _composer(store),
                const SectionHeader(label: 'running:'),
                if (snapshot.current == null)
                  const EmptyLine(text: 'idle')
                else
                  TaskRow(
                    item: snapshot.current!,
                    onTap: () => _openRun(snapshot.current!.runId),
                  ),
                if (snapshot.queue.isNotEmpty) ...[
                  SectionHeader(label: 'queued: ${snapshot.queue.length}'),
                  for (final item in snapshot.queue) QueueRow(item: item),
                ],
                SectionHeader(label: 'done: ${snapshot.done.length}'),
                if (snapshot.done.isEmpty)
                  const EmptyLine(text: 'no completed runs')
                else
                  for (final item in snapshot.done)
                    TaskRow(item: item, onTap: () => _openRun(item.runId)),
                Padding(
                  padding: const EdgeInsets.fromLTRB(12, 18, 12, 0),
                  child: Text(
                    'cost=${snapshot.totalCostLabel} · roots=${store.listing.roots.length}',
                    style: const TextStyle(color: LoopColors.muted, fontSize: 11),
                  ),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Widget _workspace(LoopStore store) {
    final root = store.selectedRoot;
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 8, 4),
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
                  fontSize: 12),
            ),
          ),
          TextButton(
            key: const Key('browse-button'),
            onPressed: store.loadingDirs ? null : _browse,
            child: Text(store.loadingDirs ? '…' : 'browse'),
          ),
        ],
      ),
    );
  }

  Widget _composer(LoopStore store) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 6, 12, 2),
      child: Column(
        children: [
          TextField(
            key: const Key('task-field'),
            controller: _task,
            minLines: 2,
            maxLines: 4,
            style: const TextStyle(color: LoopColors.strong),
            decoration: const InputDecoration(
              hintText: 'task for this workspace',
            ),
          ),
          const SizedBox(height: 8),
          Row(
            children: [
              const Expanded(
                child: Text('server-authoritative · tap a run for live logs',
                    style: TextStyle(color: LoopColors.muted, fontSize: 11)),
              ),
              FilledButton(
                key: const Key('queue-button'),
                onPressed: store.canSubmit ? _submit : null,
                child: Text(store.submitting ? 'queueing' : 'queue'),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
