// Scoped offline inspection: class and method names only; no field values.
Java.perform(function () {
  const names = Java.enumerateLoadedClassesSync().filter(n => /^com\.unitree\./.test(n));
  console.log(JSON.stringify({classes:names.sort()}));
  for (const n of names.filter(n => /web|asset|crypt|html|launch|MainActivity/i.test(n))) {
    try { console.log(JSON.stringify({name:n,methods:Java.use(n).class.getDeclaredMethods().map(x=>x.toString())})); } catch(e) {}
  }
  Java.use('android.webkit.WebView').setWebContentsDebuggingEnabled(true);
});
