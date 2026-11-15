/// One run: live tool calls plus the untruncated final summary.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'store.dart';
import 'theme.dart';
import 'widgets.dart';

class RunScreen extends StatefulWidget {
  const RunScreen({super.key, required this.store, required this.runId});

  final LoopStore store;
  final String runId;

  @override
  State<RunScreen> createState() => _RunScreenState();
}

class _RunScreenState extends State<RunScreen> {
  final ScrollController _scroll = ScrollController();
  int _lastCount = 0;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) widget.store.watchRun(widget.runId);
    });
  }

  @override
  void dispose() {
    widget.store.unwatchRun(widget.runId);
    _scroll.dispose();
    super.dispose();
  }

  void _follow(int count) {
    if (count == _lastCount) return;
    _lastCount = count;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!_scroll.hasClients) return;
      _scroll.animateTo(
        _scroll.position.maxScrollExtent,
        duration: const Duration(milliseconds: 120),
        curve: Curves.easeOut,
      );
    });
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: widget.store,
      builder: (context, _) {
        final store = widget.store;
        final log = store.runLog;
        final current = store.snapshot.current;
        final live = current?.runId == widget.runId ? current!.state : null;
        final state = live ?? log?.state ?? 'running';
        final id = log?.id.isNotEmpty == true ? log!.id : widget.runId;
        final calls = log?.callCount ?? 0;
        _follow(log?.entries.length ?? 0);
        return Scaffold(
          appBar: AppBar(
            title: Text('log · ${_short(id)}'),
          ),
          body: Column(
            children: [
              Container(
                width: double.infinity,
                padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
                decoration: const BoxDecoration(
                  border: Border(bottom: BorderSide(color: LoopColors.line)),
                ),
                child: Row(
                  children: [
                    Text(statusGlyph(state), style: TextStyle(color: statusColor(state))),
                    const SizedBox(width: 8),
                    Expanded(
                      child: Text(
                        'id=${_short(id)} · state=$state · turns=${log?.turns ?? 0} · calls=$calls',
                        style: const TextStyle(color: LoopColors.muted, fontSize: 12),
                        overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (log?.terminal == true)
                      const Text('terminal', style: TextStyle(color: LoopColors.ok, fontSize: 11)),
                  ],
                ),
              ),
              if (store.error != null) ErrorBanner(text: store.error!),
              Expanded(child: _entries(store, log)),
            ],
          ),
        );
      },
    );
  }

  Widget _entries(LoopStore store, RunLog? log) {
    if (log == null) {
      return Center(
        child: Text(store.loadingLog ? 'loading log…' : 'log unavailable',
            style: const TextStyle(color: LoopColors.muted)),
      );
    }
    if (log.entries.isEmpty) {
      return const Center(
        child: Text('waiting for events…', style: TextStyle(color: LoopColors.muted)),
      );
    }
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.only(bottom: 24),
      itemCount: log.entries.length,
      itemBuilder: (context, index) => _EntryView(entry: log.entries[index]),
    );
  }

  static String _short(String value) =>
      value.length <= 12 ? value : '…${value.substring(value.length - 8)}';
}

class _EntryView extends StatelessWidget {
  const _EntryView({required this.entry});

  final LogEntry entry;

  @override
  Widget build(BuildContext context) {
    if (entry.isCall) return _call();
    if (entry.isResult) return _result();
    if (entry.kind == 'interrupted') return _message('■ interrupted', LoopColors.warn, entry.reason);
    if (entry.kind == 'error') {
      return _message('✕ error', LoopColors.error, entry.text.isEmpty ? entry.finish : entry.text);
    }
    if (entry.kind == 'torn') return _message('■ torn', LoopColors.warn, entry.text);
    return _message('○ pending', LoopColors.muted,
        entry.text.isEmpty ? 'summary pending' : entry.text);
  }

  Widget _call() {
    final args = entry.args.isEmpty ? '' : ' — ${entry.args}';
    final obsColor = entry.failed ? LoopColors.error : LoopColors.muted;
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 9, 12, 9),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text.rich(
            TextSpan(children: [
              const TextSpan(text: '▸ ', style: TextStyle(color: LoopColors.muted)),
              TextSpan(text: 't${entry.turn} ', style: const TextStyle(color: LoopColors.muted)),
              TextSpan(text: entry.name.isEmpty ? '?' : entry.name,
                  style: const TextStyle(color: LoopColors.strong)),
              TextSpan(text: args, style: const TextStyle(color: LoopColors.body)),
            ]),
          ),
          if (entry.obs.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 4),
              child: Text('→ ${entry.obs}',
                  style: TextStyle(color: obsColor, fontSize: 12)),
            ),
        ],
      ),
    );
  }

  Widget _result() {
    final body = entry.result.isEmpty ? 'finish=${entry.finish}' : entry.result;
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 16),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Text('✓ result', style: TextStyle(color: LoopColors.ok)),
              const SizedBox(width: 8),
              Text(entry.finish,
                  style: const TextStyle(color: LoopColors.muted, fontSize: 12)),
            ],
          ),
          const SizedBox(height: 8),
          Text(body, style: const TextStyle(color: LoopColors.body, height: 1.35)),
        ],
      ),
    );
  }

  Widget _message(String head, Color color, String body) {
    return Container(
      padding: const EdgeInsets.fromLTRB(12, 12, 12, 16),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(head, style: TextStyle(color: color)),
          if (body.isNotEmpty) ...[
            const SizedBox(height: 6),
            Text(body, style: const TextStyle(color: LoopColors.body)),
          ],
        ],
      ),
    );
  }
}
