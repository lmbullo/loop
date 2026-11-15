import 'package:material_ui/material_ui.dart';

import 'home.dart';
import 'models.dart';
import 'session.dart';
import 'store.dart';
import 'theme.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  final saved = await Session.load();
  runApp(LoopApp(store: LoopStore(saved: saved), saved: saved));
}

class LoopApp extends StatelessWidget {
  const LoopApp({super.key, required this.store, this.saved});

  final LoopStore store;
  final ConnectionSettings? saved;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'loop',
      debugShowCheckedModeBanner: false,
      theme: loopTheme(),
      home: HomeScreen(store: store, saved: saved),
    );
  }
}
