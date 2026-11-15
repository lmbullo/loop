import 'package:flutter_test/flutter_test.dart';
import 'package:loop_mobile/models.dart';
import 'package:loop_mobile/session.dart';
import 'package:shared_preferences/shared_preferences.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('saves, loads and clears the last connection', () async {
    expect(await Session.load(), isNull);
    const settings =
        ConnectionSettings(host: '192.168.1.4', port: 8787, token: 't0ken');
    await Session.save(settings);
    final loaded = await Session.load();
    expect(loaded!.host, settings.host);
    expect(loaded.port, settings.port);
    expect(loaded.token, settings.token);
    await Session.clear();
    expect(await Session.load(), isNull);
  });

  test('incomplete settings are ignored', () async {
    SharedPreferences.setMockInitialValues({'loop.host': '192.168.1.4'});
    expect(await Session.load(), isNull);
  });
}
