CREATE MIGRATION m1vhz4pyyvz7lhyox5duiiesk3nqqkshr2rnstlju26dwoa7elzo4a
    ONTO m1wq26blrkrphff5h6qgjbkncgzjqb22b44rz3eghtxcuqgnjkn2lq
{
  ALTER TYPE default::Guild {
      DROP LINK channels;
  };
};
