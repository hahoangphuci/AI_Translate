import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'package:app_web_view/main.dart';

void main() {
  testWidgets('App loads splash screen', (WidgetTester tester) async {
    await tester.pumpWidget(const AITranslatorApp());
    expect(find.byType(CircularProgressIndicator), findsOneWidget);
  });
}
