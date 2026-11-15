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
          appBar: AppBar(title: Text('log · ${_short(id)}')),
          body: Column(
            children: [
              _MetaBar(
                state: state,
                text:
                    'id=${_short(id)} · state=$state · '
                    'turns=${log?.turns ?? 0} · calls=$calls',
                terminal: log?.terminal == true,
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
        child: Text(
          store.loadingLog ? 'loading log…' : 'log unavailable',
          style: LoopType.meta.copyWith(color: LoopColors.faint),
        ),
      );
    }
    if (log.entries.isEmpty) {
      return Center(
        child: Text(
          'waiting for events…',
          style: LoopType.meta.copyWith(color: LoopColors.faint),
        ),
      );
    }
    return ListView.builder(
      controller: _scroll,
      padding: const EdgeInsets.only(top: 6, bottom: LoopSpace.xl),
      itemCount: log.entries.length,
      itemBuilder: (context, index) => _EntryView(entry: log.entries[index]),
    );
  }

  static String _short(String value) =>
      value.length <= 12 ? value : '…${value.substring(value.length - 8)}';
}

class _MetaBar extends StatelessWidget {
  const _MetaBar({
    required this.state,
    required this.text,
    required this.terminal,
  });

  final String state;
  final String text;
  final bool terminal;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(LoopSpace.lg, 10, LoopSpace.lg, 10),
      decoration: const BoxDecoration(
        border: Border(bottom: BorderSide(color: LoopColors.line)),
      ),
      child: Row(
        children: [
          Text(
            statusGlyph(state),
            style: TextStyle(
              color: statusColor(state),
              fontSize: 12,
              height: 1,
            ),
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(
              text,
              style: LoopType.meta.copyWith(fontSize: 11),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (terminal)
            const Padding(
              padding: EdgeInsets.only(left: LoopSpace.sm),
              child: Text(
                'terminal',
                style: TextStyle(
                  color: LoopColors.ok,
                  fontSize: 10,
                  letterSpacing: 0.8,
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _EntryView extends StatelessWidget {
  const _EntryView({required this.entry});

  final LogEntry entry;

  @override
  Widget build(BuildContext context) {
    if (entry.isCall) return _call();
    if (entry.isResult) return _result();
    if (entry.kind == 'interrupted') {
      return _message('■ interrupted', LoopColors.warn, entry.reason);
    }
    if (entry.kind == 'error') {
      return _message(
        '✕ error',
        LoopColors.error,
        entry.text.isEmpty ? entry.finish : entry.text,
      );
    }
    if (entry.kind == 'torn') {
      return _message('■ torn', LoopColors.warn, entry.text);
    }
    return _message(
      '○ pending',
      LoopColors.muted,
      entry.text.isEmpty ? 'summary pending' : entry.text,
    );
  }

  Widget _call() {
    final args = entry.args.isEmpty ? '' : ' — ${entry.args}';
    final obsColor = entry.failed ? LoopColors.error : LoopColors.muted;
    return Padding(
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.sm,
        LoopSpace.lg,
        LoopSpace.sm,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text.rich(
            TextSpan(
              style: LoopType.body.copyWith(fontSize: 12.5, height: 1.45),
              children: [
                const TextSpan(
                  text: '▸ ',
                  style: TextStyle(color: LoopColors.faint),
                ),
                TextSpan(
                  text: 't${entry.turn} ',
                  style: const TextStyle(color: LoopColors.faint),
                ),
                TextSpan(
                  text: entry.name.isEmpty ? '?' : entry.name,
                  style: const TextStyle(color: LoopColors.strong),
                ),
                TextSpan(
                  text: args,
                  style: const TextStyle(color: LoopColors.body),
                ),
              ],
            ),
          ),
          if (entry.obs.isNotEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 3, left: 14),
              child: Text(
                '→ ${entry.obs}',
                style: TextStyle(color: obsColor, fontSize: 11.5, height: 1.4),
              ),
            ),
        ],
      ),
    );
  }

  Widget _result() {
    final body = entry.result.isEmpty ? 'finish=${entry.finish}' : entry.result;
    return _Callout(
      color: LoopColors.ok,
      head: '✓ result',
      note: entry.finish,
      body: body,
    );
  }

  Widget _message(String head, Color color, String body) {
    return _Callout(color: color, head: head, body: body);
  }
}

class _Callout extends StatelessWidget {
  const _Callout({
    required this.color,
    required this.head,
    this.note = '',
    this.body = '',
  });

  final Color color;
  final String head;
  final String note;
  final String body;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.fromLTRB(
        LoopSpace.lg,
        LoopSpace.sm,
        LoopSpace.lg,
        LoopSpace.md,
      ),
      padding: const EdgeInsets.fromLTRB(
        LoopSpace.md,
        10,
        LoopSpace.md,
        LoopSpace.md,
      ),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.05),
        border: Border(
          left: BorderSide(color: color.withValues(alpha: 0.65), width: 2),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Text(
                head,
                style: TextStyle(color: color, fontSize: 12.5, height: 1.2),
              ),
              if (note.isNotEmpty) ...[
                const SizedBox(width: LoopSpace.sm),
                Text(
                  note,
                  style: const TextStyle(
                    color: LoopColors.muted,
                    fontSize: 10.5,
                    letterSpacing: 0.6,
                  ),
                ),
              ],
            ],
          ),
          if (body.isNotEmpty) ...[
            const SizedBox(height: LoopSpace.sm),
            Text(
              body,
              style: LoopType.body.copyWith(fontSize: 13, height: 1.5),
            ),
          ],
        ],
      ),
    );
  }
}
