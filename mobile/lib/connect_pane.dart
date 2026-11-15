/// Connection setup: one private host, one port and the bridge token.
///
/// A quiet terminal login: wordmark, labelled rules, underline fields and one
/// full-width action. No filled cards around fields.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'theme.dart';
import 'widgets.dart';

class ConnectPane extends StatefulWidget {
  const ConnectPane({
    super.key,
    required this.initial,
    required this.error,
    required this.onConnect,
    this.onCancel,
  });

  final ConnectionSettings? initial;
  final String? error;
  final Future<bool> Function(String host, int port, String token) onConnect;
  final VoidCallback? onCancel;

  @override
  State<ConnectPane> createState() => _ConnectPaneState();
}

class _ConnectPaneState extends State<ConnectPane> {
  late final TextEditingController _host = TextEditingController(
    text: widget.initial?.host ?? '',
  );
  late final TextEditingController _port = TextEditingController(
    text: (widget.initial?.port ?? 8787).toString(),
  );
  late final TextEditingController _token = TextEditingController(
    text: widget.initial?.token ?? '',
  );
  bool _busy = false;

  @override
  void dispose() {
    _host.dispose();
    _port.dispose();
    _token.dispose();
    super.dispose();
  }

  Future<void> _connect() async {
    final port = int.tryParse(_port.text.trim());
    if (port == null || port < 1 || port > 65535) {
      setState(() {});
      return;
    }
    setState(() => _busy = true);
    try {
      await widget.onConnect(_host.text.trim(), port, _token.text.trim());
    } finally {
      if (mounted) setState(() => _busy = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final portBad = _busy ? false : int.tryParse(_port.text.trim()) == null;
    return ListView(
      padding: const EdgeInsets.fromLTRB(20, 24, 20, 24),
      children: [
        Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('loop', style: LoopType.wordmark),
                  SizedBox(height: 6),
                  Text('local agent tasks', style: LoopType.meta),
                ],
              ),
            ),
            if (widget.onCancel != null)
              TextButton(
                key: const Key('cancel-connect'),
                onPressed: widget.onCancel,
                child: const Text('cancel'),
              ),
          ],
        ),
        const SizedBox(height: LoopSpace.xs),
        const Text('private network only', style: LoopType.caption),
        const SizedBox(height: 28),
        const _FormLabel(label: 'bridge'),
        const SizedBox(height: LoopSpace.sm),
        TextField(
          key: const Key('host-field'),
          controller: _host,
          keyboardType: TextInputType.url,
          textInputAction: TextInputAction.next,
          autocorrect: false,
          decoration: const InputDecoration(
            labelText: 'host',
            hintText: '192.168.1.10',
          ),
          onSubmitted: (_) => FocusScope.of(context).nextFocus(),
        ),
        const SizedBox(height: LoopSpace.sm),
        TextField(
          key: const Key('port-field'),
          controller: _port,
          keyboardType: TextInputType.number,
          textInputAction: TextInputAction.next,
          onChanged: (_) => setState(() {}),
          decoration: InputDecoration(
            labelText: 'port',
            hintText: '8787',
            errorText: portBad ? '1..65535' : null,
          ),
          onSubmitted: (_) => FocusScope.of(context).nextFocus(),
        ),
        const SizedBox(height: LoopSpace.sm),
        TextField(
          key: const Key('token-field'),
          controller: _token,
          obscureText: true,
          autocorrect: false,
          enableSuggestions: false,
          textInputAction: TextInputAction.done,
          decoration: const InputDecoration(labelText: 'token'),
          onSubmitted: (_) {
            if (!_busy) _connect();
          },
        ),
        if (widget.error != null) ...[
          const SizedBox(height: LoopSpace.md),
          Text(
            '✕ ${widget.error}',
            style: const TextStyle(
              color: LoopColors.error,
              fontSize: 12,
              height: 1.4,
            ),
          ),
        ],
        const SizedBox(height: 20),
        SizedBox(
          width: double.infinity,
          height: 44,
          child: FilledButton(
            key: const Key('connect-button'),
            onPressed: _busy ? null : _connect,
            child: Text(_busy ? 'connecting' : 'connect'),
          ),
        ),
        const SizedBox(height: 28),
        const Hairline(),
        const SizedBox(height: LoopSpace.md),
        const Text('start the bridge', style: LoopType.caption),
        const SizedBox(height: 6),
        const Text(
          'python3 run.py server mobile start',
          style: TextStyle(color: LoopColors.body, fontSize: 11.5, height: 1.6),
        ),
        const SizedBox(height: LoopSpace.xs),
        const Text(
          'use the addr and token it prints. the bridge binds one private IP '
          'and requires the bearer token for every request.',
          style: TextStyle(color: LoopColors.faint, fontSize: 11, height: 1.6),
        ),
      ],
    );
  }
}

class _FormLabel extends StatelessWidget {
  const _FormLabel({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Text(label, style: LoopType.label),
        const SizedBox(width: 10),
        const Expanded(child: Hairline()),
      ],
    );
  }
}
