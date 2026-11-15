/// Connection setup: one private host, one port and the bridge token.
library;

import 'package:material_ui/material_ui.dart';

import 'models.dart';
import 'theme.dart';

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
  late final TextEditingController _host =
      TextEditingController(text: widget.initial?.host ?? '');
  late final TextEditingController _port =
      TextEditingController(text: (widget.initial?.port ?? 8787).toString());
  late final TextEditingController _token =
      TextEditingController(text: widget.initial?.token ?? '');
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
      padding: const EdgeInsets.all(16),
      children: [
        const Text('loop', style: TextStyle(fontSize: 22, color: LoopColors.strong)),
        const SizedBox(height: 4),
        Row(
          children: [
            const Expanded(
              child: Text('local agent tasks · private network only',
                  style: TextStyle(color: LoopColors.muted, fontSize: 12)),
            ),
            if (widget.onCancel != null)
              TextButton(
                key: const Key('cancel-connect'),
                onPressed: widget.onCancel,
                child: const Text('cancel'),
              ),
          ],
        ),
        const SizedBox(height: 24),
        TextField(
          key: const Key('host-field'),
          controller: _host,
          keyboardType: TextInputType.url,
          decoration: const InputDecoration(
            labelText: 'host',
            hintText: '192.168.1.10',
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('port-field'),
          controller: _port,
          keyboardType: TextInputType.number,
          onChanged: (_) => setState(() {}),
          decoration: InputDecoration(
            labelText: 'port',
            errorText: portBad ? '1..65535' : null,
          ),
        ),
        const SizedBox(height: 12),
        TextField(
          key: const Key('token-field'),
          controller: _token,
          obscureText: true,
          autocorrect: false,
          enableSuggestions: false,
          decoration: const InputDecoration(labelText: 'token'),
        ),
        if (widget.error != null) ...[
          const SizedBox(height: 12),
          Text('✕ ${widget.error}',
              style: const TextStyle(color: LoopColors.error, fontSize: 12)),
        ],
        const SizedBox(height: 16),
        FilledButton(
          key: const Key('connect-button'),
          onPressed: _busy ? null : _connect,
          child: Text(_busy ? 'connecting' : 'connect'),
        ),
        const SizedBox(height: 16),
        const Text(
          'run: python3 run.py server mobile start\n'
          'use the addr and token it prints; the bridge binds one private IP '
          'and requires the bearer token for every request.',
          style: TextStyle(color: LoopColors.muted, fontSize: 11, height: 1.5),
        ),
      ],
    );
  }
}
