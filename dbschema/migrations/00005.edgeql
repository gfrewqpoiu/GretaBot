CREATE MIGRATION m1qalnignwwao3azkexokf7tyuvbblecdwzhsbml7jst4cjv2eczlq
    ONTO m1vhz4pyyvz7lhyox5duiiesk3nqqkshr2rnstlju26dwoa7elzo4a
{
  ALTER TYPE default::Guild {
      CREATE MULTI LINK channels := (.<guild[IS default::GuildChannel]);
  };
};
