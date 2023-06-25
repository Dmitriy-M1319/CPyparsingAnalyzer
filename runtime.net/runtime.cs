using System;


namespace CompilerDemo {

  class Runtime {
    public static string read() {
      return Console.ReadLine();
    }

    public static void print(string p0) {
      Console.Write(p0);
    }

    public static void println(string p0) {
      Console.WriteLine(p0);
    }

    public static int to_int(string p0) {
      return Convert.ToInt32(p0);
    }

    public static double to_float(string p0) {
      return Convert.ToDouble(p0);
    }

    public static string convert(int v) {
      return Convert.ToString(v);
    }

    public static string convert(double v) {
      return Convert.ToString(v);
    }

    public static string convert(bool v) {
      return Convert.ToString(v);
    }

    public static string concat(string a, string b) {
      return a + b;
    }

    public static int compare(string a, string b) {
      return a.CompareTo(b);
    }
  }
}
